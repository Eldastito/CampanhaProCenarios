"""Repositório do domínio político-eleitoral.

Concentra operações sobre PoliticalProject (Fase 1) e auxiliares de
auditoria/alerta usados pelos guardrails (Fase 7).
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.political import (
    PoliticalAgentProfile,
    PoliticalAuditLog,
    PoliticalComplianceAlert,
    PoliticalEvidenceSource,
    PoliticalProject,
)


class PoliticalProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, project: PoliticalProject) -> PoliticalProject:
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_by_id(self, project_id: str) -> PoliticalProject | None:
        return (
            self.db.query(PoliticalProject)
            .filter(PoliticalProject.id == project_id)
            .first()
        )

    def list_for_org(
        self,
        organization_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PoliticalProject]:
        return (
            self.db.query(PoliticalProject)
            .filter(PoliticalProject.organization_id == organization_id)
            .order_by(PoliticalProject.created_at.desc(), PoliticalProject.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update(self, project: PoliticalProject) -> PoliticalProject:
        self.db.commit()
        self.db.refresh(project)
        return project

    def delete(self, project: PoliticalProject) -> None:
        self.db.delete(project)
        self.db.commit()

    def count_distinct_campaigns(self, organization_id: str) -> int:
        """Conta campanhas distintas (campaign_id) com pelo menos um projeto na organização.

        Usado pela quota MVP (10 campanhas simultâneas / org). Conta DISTINCT
        em vez de linhas para que múltiplos projetos da mesma campanha não
        consumam slots adicionais.
        """
        return (
            self.db.query(func.count(func.distinct(PoliticalProject.campaign_id)))
            .filter(PoliticalProject.organization_id == organization_id)
            .scalar()
            or 0
        )

    def has_campaign(self, organization_id: str, campaign_id: str) -> bool:
        return (
            self.db.query(PoliticalProject.id)
            .filter(
                PoliticalProject.organization_id == organization_id,
                PoliticalProject.campaign_id == campaign_id,
            )
            .first()
            is not None
        )


class PoliticalEvidenceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, evidence: PoliticalEvidenceSource) -> PoliticalEvidenceSource:
        self.db.add(evidence)
        self.db.commit()
        self.db.refresh(evidence)
        return evidence

    def get_by_id(self, evidence_id: str) -> PoliticalEvidenceSource | None:
        return (
            self.db.query(PoliticalEvidenceSource)
            .filter(PoliticalEvidenceSource.id == evidence_id)
            .first()
        )

    def list_for_project(
        self,
        project_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PoliticalEvidenceSource]:
        return (
            self.db.query(PoliticalEvidenceSource)
            .filter(PoliticalEvidenceSource.project_id == project_id)
            .order_by(PoliticalEvidenceSource.collected_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )


class PoliticalComplianceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, alert: PoliticalComplianceAlert) -> PoliticalComplianceAlert:
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def list_for_org(
        self,
        organization_id: str,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PoliticalComplianceAlert]:
        query = self.db.query(PoliticalComplianceAlert).filter(
            PoliticalComplianceAlert.organization_id == organization_id
        )
        if status:
            query = query.filter(PoliticalComplianceAlert.status == status)
        return (
            query.order_by(PoliticalComplianceAlert.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )


class PoliticalAgentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, agent: PoliticalAgentProfile) -> PoliticalAgentProfile:
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def add_bulk(self, agents: list[PoliticalAgentProfile]) -> list[PoliticalAgentProfile]:
        if not agents:
            return []
        self.db.add_all(agents)
        self.db.commit()
        for a in agents:
            self.db.refresh(a)
        return agents

    def get_by_id(self, agent_id: str) -> PoliticalAgentProfile | None:
        return (
            self.db.query(PoliticalAgentProfile)
            .filter(PoliticalAgentProfile.id == agent_id)
            .first()
        )

    def list_for_project(
        self,
        project_id: str,
        agent_type: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[PoliticalAgentProfile]:
        query = self.db.query(PoliticalAgentProfile).filter(
            PoliticalAgentProfile.project_id == project_id
        )
        if agent_type:
            query = query.filter(PoliticalAgentProfile.agent_type == agent_type)
        return (
            query.order_by(
                PoliticalAgentProfile.agent_type.asc(),
                PoliticalAgentProfile.category.asc(),
                PoliticalAgentProfile.created_at.asc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

    def categories_present(self, project_id: str, agent_type: str) -> set[str]:
        rows = (
            self.db.query(PoliticalAgentProfile.category)
            .filter(
                PoliticalAgentProfile.project_id == project_id,
                PoliticalAgentProfile.agent_type == agent_type,
            )
            .all()
        )
        return {r[0] for r in rows}

    def delete_generated_for_project(self, project_id: str) -> int:
        """Remove agentes do tipo 'generated' (mantém os fixos). Retorna nº removidos."""
        result = (
            self.db.query(PoliticalAgentProfile)
            .filter(
                PoliticalAgentProfile.project_id == project_id,
                PoliticalAgentProfile.agent_type == "generated",
            )
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return result or 0


class PoliticalAuditLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, log: PoliticalAuditLog) -> PoliticalAuditLog:
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def list_for_project(
        self,
        project_id: str,
        limit: int = 200,
        offset: int = 0,
    ) -> list[PoliticalAuditLog]:
        return (
            self.db.query(PoliticalAuditLog)
            .filter(PoliticalAuditLog.project_id == project_id)
            .order_by(PoliticalAuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
