"""Repositório do domínio político-eleitoral.

Concentra operações sobre PoliticalProject (Fase 1) e auxiliares de
auditoria/alerta usados pelos guardrails (Fase 7).
"""

from sqlalchemy.orm import Session

from app.models.political import (
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
