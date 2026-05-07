"""Endpoints de evidências políticas (Fase 2).

Aceita upload de arquivo (PDF/TXT/MD/CSV) ou cadastro manual via JSON
(textos colados, links). Cada evidência fica vinculada a um projeto e a uma
organização. Dedup por content_hash evita duplicatas no mesmo projeto.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps.auth import require_analyst
from app.models.political import PoliticalProject
from app.models.user import User
from app.repositories.political_repository import (
    PoliticalEvidenceRepository,
    PoliticalProjectRepository,
)
from app.schemas.political import (
    PoliticalEvidenceManualCreate,
    PoliticalEvidenceSourceResponse,
)
from app.services.evidence_ingestion_service import (
    EvidenceIngestionService,
    EvidenceUploadInput,
)

logger = logging.getLogger(__name__)
router = APIRouter()


_FILE_TYPE_MAP = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/x-markdown": "md",
    "text/csv": "csv",
    "application/csv": "csv",
}


def _ensure_project(project_id: str, db: Session, user: User) -> PoliticalProject:
    project = PoliticalProjectRepository(db).get_by_id(project_id)
    if project is None or project.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado.")
    return project


def _detect_source_type(upload: UploadFile) -> str:
    if upload.content_type and upload.content_type in _FILE_TYPE_MAP:
        return _FILE_TYPE_MAP[upload.content_type]
    name = (upload.filename or "").lower()
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith(".csv"):
        return "csv"
    if name.endswith(".md") or name.endswith(".markdown"):
        return "md"
    if name.endswith(".txt"):
        return "txt"
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=(
            "Tipo de arquivo não suportado. Aceitos: PDF, TXT, MD, CSV. "
            f"Recebido content-type={upload.content_type!r}, filename={upload.filename!r}"
        ),
    )


@router.post(
    "/projects/{project_id}/evidence",
    response_model=PoliticalEvidenceSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de evidência (arquivo PDF/TXT/MD/CSV)",
)
async def upload_evidence_file(
    project_id: str,
    file: Annotated[UploadFile, File(...)],
    title: Annotated[str, Form(...)],
    source_name: Annotated[str | None, Form()] = None,
    source_url: Annotated[str | None, Form()] = None,
    author: Annotated[str | None, Form()] = None,
    published_at: Annotated[str | None, Form(description="ISO 8601 datetime")] = None,
    reliability_override: Annotated[str | None, Form()] = None,
    metadata_json: Annotated[str | None, Form(description="JSON livre")] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> PoliticalEvidenceSourceResponse:
    project = _ensure_project(project_id, db, user)
    source_type = _detect_source_type(file)
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo vazio.",
        )

    extra_meta: dict = {}
    if metadata_json:
        try:
            parsed = json.loads(metadata_json)
            if isinstance(parsed, dict):
                extra_meta.update(parsed)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="metadata_json não é um JSON válido.",
            )
    extra_meta.setdefault("upload_filename", file.filename)
    extra_meta.setdefault("upload_content_type", file.content_type)
    extra_meta.setdefault("upload_size_bytes", len(content))

    pub_at = _parse_datetime(published_at)

    service = EvidenceIngestionService(db)
    record, created = service.ingest(
        EvidenceUploadInput(
            project=project,
            title=title,
            source_type=source_type,
            actor_user_id=user.id,
            content=content,
            source_name=source_name or file.filename,
            source_url=source_url,
            author=author,
            published_at=pub_at,
            reliability_override=reliability_override,
            metadata=extra_meta,
        )
    )
    logger.info(
        "evidence_upload project=%s evidence=%s created=%s",
        project.id, record.id, created,
    )
    return PoliticalEvidenceSourceResponse.model_validate(record)


@router.post(
    "/projects/{project_id}/evidence/manual",
    response_model=PoliticalEvidenceSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar evidência manualmente (texto colado ou link)",
)
def upload_evidence_manual(
    project_id: str,
    body: PoliticalEvidenceManualCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> PoliticalEvidenceSourceResponse:
    project = _ensure_project(project_id, db, user)
    service = EvidenceIngestionService(db)
    record, _created = service.ingest(
        EvidenceUploadInput(
            project=project,
            title=body.title,
            source_type=body.source_type,
            actor_user_id=user.id,
            raw_text_manual=body.raw_text,
            source_name=body.source_name,
            source_url=body.source_url,
            author=body.author,
            published_at=body.published_at,
            reliability_override=body.reliability_override,
            metadata=body.metadata or {},
        )
    )
    return PoliticalEvidenceSourceResponse.model_validate(record)


@router.get(
    "/projects/{project_id}/evidence",
    response_model=list[PoliticalEvidenceSourceResponse],
    summary="Listar evidências de um projeto",
)
def list_evidence(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[PoliticalEvidenceSourceResponse]:
    project = _ensure_project(project_id, db, user)
    items = PoliticalEvidenceRepository(db).list_for_project(
        project.id, limit=limit, offset=offset
    )
    return [PoliticalEvidenceSourceResponse.model_validate(e) for e in items]


@router.get(
    "/evidence/{evidence_id}",
    response_model=PoliticalEvidenceSourceResponse,
    summary="Obter detalhes de uma evidência",
)
def get_evidence(
    evidence_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> PoliticalEvidenceSourceResponse:
    record = PoliticalEvidenceRepository(db).get_by_id(evidence_id)
    if record is None or record.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidência não encontrada.")
    return PoliticalEvidenceSourceResponse.model_validate(record)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # aceita 'YYYY-MM-DD' ou ISO completo
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"published_at inválido (esperado ISO 8601): {value!r}",
        )
