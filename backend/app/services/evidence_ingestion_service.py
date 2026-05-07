"""Ingestão de evidências políticas: upload de arquivo/manual, hash, dedup,
extração de texto, classificação de confiabilidade e persistência.

Fluxo (PRD §RF-02):
1. Recebe bytes (ou texto manual) + metadados
2. Calcula content_hash (sha256) → dedup por projeto
3. Persiste arquivo no StorageProvider (estrutura {org}/{project}/{evidence_id}.{ext})
4. Extrai texto conforme source_type
5. Classifica confiabilidade (SourceVerificationService)
6. Salva PoliticalEvidenceSource com status 'ready' (ou 'failed' se extração falhar)
7. Emite ComplianceAlert se a fonte for fraca
8. Registra audit log

Idempotência: ao detectar content_hash duplicado para o mesmo projeto, retorna
o registro existente sem duplicar arquivo nem alerta.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.political import (
    PoliticalAuditLog,
    PoliticalEvidenceSource,
    PoliticalProject,
)
from app.repositories.political_repository import (
    PoliticalAuditLogRepository,
    PoliticalEvidenceRepository,
)
from app.services.source_verification_service import (
    ReliabilityClassification,
    SourceVerificationService,
    classify_reliability,
)
from app.services.storage.base import StorageProvider
from app.services.storage.local import LocalFilesystemStorageProvider
from app.services.text_extractor import extract_text

logger = logging.getLogger(__name__)


_VALID_SOURCE_TYPES = {"pdf", "txt", "md", "markdown", "csv", "link", "manual"}


@dataclass
class EvidenceUploadInput:
    project: PoliticalProject
    title: str
    source_type: str
    actor_user_id: str | None
    content: bytes | None = None
    raw_text_manual: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    reliability_override: str | None = None
    metadata: dict | None = None


class EvidenceIngestionService:
    def __init__(
        self,
        db: Session,
        *,
        storage: StorageProvider | None = None,
    ) -> None:
        self.db = db
        self._repo = PoliticalEvidenceRepository(db)
        self._audit = PoliticalAuditLogRepository(db)
        self._verifier = SourceVerificationService(db)
        self._storage = storage or LocalFilesystemStorageProvider("./storage")

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def ingest(self, payload: EvidenceUploadInput) -> tuple[PoliticalEvidenceSource, bool]:
        """Persiste a evidência. Retorna (registro, created_now).

        ``created_now=False`` indica que o conteúdo (mesmo hash) já existia
        no projeto e o registro retornado é o existente.
        """
        stype = (payload.source_type or "").lower().strip()
        if stype == "markdown":
            stype = "md"
        if stype not in _VALID_SOURCE_TYPES:
            raise ValueError(
                f"source_type inválido: {payload.source_type!r}. "
                f"Esperado um de: {sorted(_VALID_SOURCE_TYPES)}"
            )

        # Para tipos manuais, content é o raw_text_manual em bytes
        body_bytes = payload.content
        if body_bytes is None and payload.raw_text_manual is not None:
            body_bytes = payload.raw_text_manual.encode("utf-8")
        if body_bytes is None:
            if stype == "link":
                # links não exigem corpo de arquivo; usa source_url + title como conteúdo lógico
                body_bytes = (payload.source_url or payload.title).encode("utf-8")
            else:
                raise ValueError("Conteúdo vazio: forneça arquivo (content) ou raw_text_manual.")

        content_hash = hashlib.sha256(body_bytes).hexdigest()

        # Dedup dentro do projeto
        existing = self._find_existing_by_hash(payload.project.id, content_hash)
        if existing is not None:
            logger.info(
                "evidence_dedup_hit project=%s hash=%s existing_id=%s",
                payload.project.id,
                content_hash[:12],
                existing.id,
            )
            return existing, False

        evidence_id = str(uuid4())

        # Extrai texto antes de persistir o registro (para usar na classificação)
        extraction = extract_text(body_bytes, stype, filename=payload.source_name)
        raw_text = extraction.text or None

        # Storage: salva binário em {org}/{project}/{evidence_id}.{ext}
        ext = stype if stype not in {"link", "manual"} else "txt"
        storage_path = f"{payload.project.organization_id}/{payload.project.id}/{evidence_id}.{ext}"
        try:
            storage_uri = self._storage.save_bytes(storage_path, body_bytes)
            processing_status = "ready"
            processing_error: str | None = None
        except Exception as e:  # noqa: BLE001
            logger.exception("evidence_storage_failed")
            storage_uri = None
            processing_status = "failed"
            processing_error = f"Falha ao salvar arquivo: {e}"

        # Classificação de confiabilidade
        if payload.reliability_override:
            reliability = payload.reliability_override
            classification_rationale = "Confiabilidade definida manualmente."
        else:
            cls = classify_reliability(
                source_type=stype,
                source_url=payload.source_url,
                source_name=payload.source_name,
                raw_text_sample=raw_text,
            )
            reliability = cls.level
            classification_rationale = cls.rationale

        # Monta metadata enriquecida
        metadata: dict = dict(payload.metadata or {})
        metadata["extraction"] = {
            "method": extraction.extraction_method,
            "page_count": extraction.page_count,
            "warnings": list(extraction.warnings),
        }
        metadata["classification_rationale"] = classification_rationale
        if processing_error:
            metadata["processing_error"] = processing_error

        record = PoliticalEvidenceSource(
            id=evidence_id,
            organization_id=payload.project.organization_id,
            project_id=payload.project.id,
            title=payload.title,
            source_type=stype,
            source_name=payload.source_name,
            source_url=payload.source_url,
            author=payload.author,
            published_at=payload.published_at,
            reliability_level=reliability,
            content_hash=content_hash,
            storage_uri=storage_uri,
            raw_text=raw_text,
            metadata_json=metadata,
            processing_status=processing_status,
            processing_error=processing_error,
            created_by=payload.actor_user_id,
        )
        saved = self._repo.add(record)

        # Alerta de compliance para fontes fracas
        self._verifier.emit_weak_source_alert_if_needed(
            organization_id=saved.organization_id,
            project_id=saved.project_id,
            evidence_id=saved.id,
            classification=ReliabilityClassification(
                level=reliability,
                score=0,  # score não usado no alerta
                rationale=classification_rationale,
            ),
            source_title=saved.title,
        )

        # Audit log
        self._audit.add(
            PoliticalAuditLog(
                id=str(uuid4()),
                organization_id=saved.organization_id,
                project_id=saved.project_id,
                actor_user_id=payload.actor_user_id,
                action="political_evidence.uploaded",
                target_type="political_evidence_source",
                target_id=saved.id,
                payload={
                    "title": saved.title,
                    "source_type": saved.source_type,
                    "reliability_level": saved.reliability_level,
                    "content_hash": saved.content_hash,
                    "extraction_method": extraction.extraction_method,
                },
            )
        )

        return saved, True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _find_existing_by_hash(
        self, project_id: str, content_hash: str
    ) -> PoliticalEvidenceSource | None:
        return (
            self.db.query(PoliticalEvidenceSource)
            .filter(
                PoliticalEvidenceSource.project_id == project_id,
                PoliticalEvidenceSource.content_hash == content_hash,
            )
            .first()
        )
