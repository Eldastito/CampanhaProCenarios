"""Endpoint de exportação de relatórios (Fase 5 PRD v2).

POST /api/v1/political/projects/{project_id}/reports
body: {
  "type": "executive_summary" | "factor_deep_dive" | ... ,
  "format": "pdf" | "docx",
  "context": {  # opcional, depende do tipo:
    "scenario_id": "...",       # scenario_what_if
    "election_result_id": "...", # candidate_comparison
    "dossier_id": "..."         # dossier_export
  }
}
→ streaming binário com Content-Type apropriado e header de download.
"""

from __future__ import annotations

import logging
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.scenario_catalog import ELECTORAL_FACTORS
from app.db.session import get_db
from app.deps.auth import require_analyst
from app.models.dossier import CandidateDossier
from app.models.election_probability import ElectionProbabilityResult
from app.models.political import PoliticalAuditLog, PoliticalComplianceAlert
from app.models.scenario import Scenario
from app.models.user import User
from app.repositories.factor_cache_repository import CampanhaProFactorCacheRepository
from app.repositories.political_repository import PoliticalProjectRepository
from app.services import report_service

logger = logging.getLogger(__name__)
router = APIRouter()


ReportType = Literal[
    "executive_summary",
    "factor_deep_dive",
    "candidate_comparison",
    "scenario_what_if",
    "compliance_audit",
    "dossier_export",
]


class ReportRequest(BaseModel):
    type: ReportType
    format: Literal["pdf", "docx"] = "pdf"
    context: dict | None = Field(default=None)


def _audit(db, *, organization_id, project_id, actor_user_id, action, payload):
    db.add(
        PoliticalAuditLog(
            id=str(uuid4()),
            organization_id=organization_id,
            project_id=project_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type="report",
            target_id=None,
            payload=payload,
        )
    )
    db.commit()


@router.post(
    "",
    summary="Gerar relatório PDF/DOCX",
)
def generate_report(
    project_id: str,
    body: ReportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> Response:
    project = PoliticalProjectRepository(db).get_by_id(project_id)
    if project is None or project.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado.")

    extra_ctx = body.context or {}

    if body.type == "executive_summary":
        cache = CampanhaProFactorCacheRepository(db).latest_for_project(
            user.organization_id, project.id
        )
        latest_factors = (
            {
                "factors": cache.factors,
                "coverage_percent": cache.coverage_percent,
            }
            if cache
            else None
        )
        latest_election = (
            db.query(ElectionProbabilityResult)
            .filter(
                ElectionProbabilityResult.political_project_id == project.id,
                ElectionProbabilityResult.status == "completed",
            )
            .order_by(ElectionProbabilityResult.created_at.desc())
            .first()
        )
        latest_election_dict = (
            {"output_results": latest_election.output_results} if latest_election else None
        )
        alerts = (
            db.query(PoliticalComplianceAlert)
            .filter(
                PoliticalComplianceAlert.organization_id == user.organization_id,
                PoliticalComplianceAlert.project_id == project.id,
                PoliticalComplianceAlert.status == "open",
            )
            .order_by(PoliticalComplianceAlert.created_at.desc())
            .all()
        )
        context = report_service.build_executive_summary_context(
            project,
            latest_factors=latest_factors,
            latest_election=latest_election_dict,
            alerts=alerts,
            factor_catalog=list(ELECTORAL_FACTORS),
        )

    elif body.type == "factor_deep_dive":
        cache = CampanhaProFactorCacheRepository(db).latest_for_project(
            user.organization_id, project.id
        )
        context = report_service.build_factor_deep_dive_context(
            project, cache=cache, factor_catalog=list(ELECTORAL_FACTORS)
        )

    elif body.type == "candidate_comparison":
        result_id = extra_ctx.get("election_result_id")
        if not result_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="context.election_result_id é obrigatório para candidate_comparison.",
            )
        row = (
            db.query(ElectionProbabilityResult)
            .filter(
                ElectionProbabilityResult.id == result_id,
                ElectionProbabilityResult.political_project_id == project.id,
            )
            .first()
        )
        if row is None or row.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resultado de Monte Carlo não encontrado ou ainda não finalizado.",
            )
        context = report_service.build_candidate_comparison_context(project, election_result=row)

    elif body.type == "scenario_what_if":
        scenario_id = extra_ctx.get("scenario_id")
        if not scenario_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="context.scenario_id é obrigatório para scenario_what_if.",
            )
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if scenario is None or scenario.organization_id != user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cenário não encontrado."
            )
        # Decomposição simples por fator a partir do baseline/alternative inputs.
        catalog = {f.key: f for f in ELECTORAL_FACTORS}
        breakdown = []
        for k, f in catalog.items():
            b = (scenario.baseline_inputs or {}).get(k)
            a = (scenario.alternative_inputs or {}).get(k)
            direction = "→"
            if a is not None and b is not None:
                if a > b:
                    direction = "↑"
                elif a < b:
                    direction = "↓"
            breakdown.append(
                {"label": f.label, "baseline_value": b, "alternative_value": a, "direction": direction}
            )
        context = report_service.build_scenario_what_if_context(
            project, scenario=scenario, factor_breakdown=breakdown
        )

    elif body.type == "compliance_audit":
        alerts = (
            db.query(PoliticalComplianceAlert)
            .filter(
                PoliticalComplianceAlert.organization_id == user.organization_id,
                PoliticalComplianceAlert.project_id == project.id,
                PoliticalComplianceAlert.status == "open",
            )
            .order_by(PoliticalComplianceAlert.created_at.desc())
            .all()
        )
        context = report_service.build_compliance_audit_context(project, alerts=alerts)

    elif body.type == "dossier_export":
        dossier_id = extra_ctx.get("dossier_id")
        if not dossier_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="context.dossier_id é obrigatório para dossier_export.",
            )
        dossier = (
            db.query(CandidateDossier)
            .filter(
                CandidateDossier.id == dossier_id,
                CandidateDossier.political_project_id == project.id,
            )
            .first()
        )
        if dossier is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Dossiê não encontrado."
            )
        context = report_service.build_dossier_export_context(project, dossier=dossier)

    else:  # pragma: no cover — defensive
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo desconhecido: {body.type}",
        )

    # Renderiza HTML uma vez (usado por PDF e diagnóstico).
    html = report_service.render_html(body.type, context)

    filename_safe = f"{body.type}_{project.id[:8]}"
    if body.format == "pdf":
        if not report_service.PDF_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "PDF indisponível neste ambiente — WeasyPrint requer "
                    "libpango/libcairo no host. Use format=docx ou rode em "
                    "container com as deps."
                ),
            )
        try:
            payload = report_service.html_to_pdf(html)
        except Exception as exc:  # noqa: BLE001
            logger.exception("pdf_render_failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Falha ao renderizar PDF: {exc}",
            ) from exc
        content_type = "application/pdf"
        ext = "pdf"
    else:
        if not report_service.DOCX_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DOCX indisponível: python-docx não instalado.",
            )
        payload = report_service.build_docx(body.type, context)
        content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        ext = "docx"

    _audit(
        db,
        organization_id=user.organization_id,
        project_id=project.id,
        actor_user_id=user.id,
        action="report.exported",
        payload={
            "type": body.type,
            "format": body.format,
            "size_bytes": len(payload),
        },
    )

    return Response(
        content=payload,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename_safe}.{ext}"',
        },
    )
