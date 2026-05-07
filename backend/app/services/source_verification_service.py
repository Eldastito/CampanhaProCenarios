"""Classificação de confiabilidade de fontes + emissão de alertas de compliance.

Níveis de confiabilidade (PRD §RF-03):
- official            órgãos oficiais, TSE, IBGE, ministérios, prefeituras
- press               imprensa reconhecida
- registered_poll     pesquisas eleitorais com registro no TSE
- public_base         bases públicas estruturadas
- internal            documentos internos da campanha
- social              mídia social, posts não verificados
- unverified          fonte sem classificação clara (default)

Heurísticas (Fase 2): inferência por URL/domínio + tipo de fonte.
Pode ser refinada na Fase 7 com modelagem mais robusta.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.political import PoliticalComplianceAlert
from app.repositories.political_repository import PoliticalComplianceRepository

logger = logging.getLogger(__name__)


RELIABILITY_LEVELS = {
    "official": 5,
    "press": 4,
    "registered_poll": 4,
    "public_base": 4,
    "internal": 3,
    "social": 2,
    "unverified": 1,
}


_OFFICIAL_DOMAINS = (
    "tse.jus.br", "stf.jus.br", "stj.jus.br", "tcu.gov.br",
    "ibge.gov.br", "datasus.gov.br", "gov.br",
    "presidencia.gov.br", "planalto.gov.br",
    "camara.leg.br", "senado.leg.br", "senado.gov.br",
    "tribunais.jus.br", "ipea.gov.br", "anpd.gov.br",
)

_PRESS_DOMAINS = (
    "g1.globo.com", "globo.com", "folha.uol.com.br", "uol.com.br",
    "estadao.com.br", "valor.globo.com", "bbc.com", "reuters.com",
    "ap.org", "cnnbrasil.com.br", "veja.abril.com.br", "exame.com",
    "oglobo.globo.com", "nexojornal.com.br", "agenciapublica.org",
)

_SOCIAL_DOMAINS = (
    "twitter.com", "x.com", "instagram.com", "facebook.com",
    "tiktok.com", "youtube.com", "telegram.org", "t.me",
    "whatsapp.com", "reddit.com",
)

_REGISTERED_POLL_HINTS = re.compile(
    r"\b(registr[oa] tse|nº? *tse-\d|registro nº?|cnpj.*pesquisa)\b",
    flags=re.IGNORECASE,
)


@dataclass
class ReliabilityClassification:
    level: str
    score: int
    rationale: str


def classify_reliability(
    *,
    source_type: str,
    source_url: str | None = None,
    source_name: str | None = None,
    raw_text_sample: str | None = None,
) -> ReliabilityClassification:
    """Classifica a confiabilidade de uma fonte. Não levanta exceção; sempre devolve um nível."""
    stype = (source_type or "").lower().strip()

    # Documentos internos manuais
    if stype in {"manual", "internal"}:
        return ReliabilityClassification(
            level="internal",
            score=RELIABILITY_LEVELS["internal"],
            rationale="Marcado como documento interno da campanha.",
        )

    domain = _domain_of(source_url)

    if domain:
        if any(domain.endswith(d) for d in _OFFICIAL_DOMAINS):
            return ReliabilityClassification(
                level="official",
                score=RELIABILITY_LEVELS["official"],
                rationale=f"Domínio oficial reconhecido: {domain}",
            )
        if any(domain.endswith(d) for d in _PRESS_DOMAINS):
            return ReliabilityClassification(
                level="press",
                score=RELIABILITY_LEVELS["press"],
                rationale=f"Imprensa reconhecida: {domain}",
            )
        if any(domain.endswith(d) for d in _SOCIAL_DOMAINS):
            return ReliabilityClassification(
                level="social",
                score=RELIABILITY_LEVELS["social"],
                rationale=f"Conteúdo de mídia social: {domain}",
            )

    # Pesquisas registradas no TSE — heurística por texto
    sample = (raw_text_sample or "")[:5000]
    if sample and _REGISTERED_POLL_HINTS.search(sample):
        return ReliabilityClassification(
            level="registered_poll",
            score=RELIABILITY_LEVELS["registered_poll"],
            rationale="Texto contém indícios de pesquisa registrada no TSE.",
        )

    if stype == "csv":
        return ReliabilityClassification(
            level="public_base",
            score=RELIABILITY_LEVELS["public_base"],
            rationale="Tabela estruturada (CSV) tratada como base pública por padrão.",
        )

    return ReliabilityClassification(
        level="unverified",
        score=RELIABILITY_LEVELS["unverified"],
        rationale="Não foi possível inferir confiabilidade — fica como não verificada.",
    )


def _domain_of(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return (parsed.hostname or "").lower() or None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Compliance alerts
# ---------------------------------------------------------------------------


class SourceVerificationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._alerts = PoliticalComplianceRepository(db)

    def emit_weak_source_alert_if_needed(
        self,
        *,
        organization_id: str,
        project_id: str,
        evidence_id: str,
        classification: ReliabilityClassification,
        source_title: str,
    ) -> PoliticalComplianceAlert | None:
        """Emite alerta de compliance se a fonte for fraca (social/unverified)."""
        if classification.level not in {"social", "unverified"}:
            return None

        severity = "high" if classification.level == "unverified" else "medium"
        alert = PoliticalComplianceAlert(
            id=str(uuid4()),
            organization_id=organization_id,
            project_id=project_id,
            alert_type="weak_source",
            severity=severity,
            message=(
                f"Fonte de confiabilidade '{classification.level}' detectada em '{source_title}'. "
                "Conclusões baseadas nesta fonte devem ser marcadas como hipótese, não como fato."
            ),
            related_entity_type="political_evidence_source",
            related_entity_id=evidence_id,
            context={
                "reliability_level": classification.level,
                "rationale": classification.rationale,
            },
        )
        return self._alerts.add(alert)
