"""Repositório do cache de fatores derivado de snapshots CampanhaPro."""

from sqlalchemy.orm import Session

from app.models.factor_cache import CampanhaProFactorCache


class CampanhaProFactorCacheRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, cache: CampanhaProFactorCache) -> CampanhaProFactorCache:
        self.db.add(cache)
        self.db.commit()
        self.db.refresh(cache)
        return cache

    def get_by_snapshot(self, snapshot_id: str) -> CampanhaProFactorCache | None:
        return (
            self.db.query(CampanhaProFactorCache)
            .filter(CampanhaProFactorCache.snapshot_id == snapshot_id)
            .first()
        )

    def latest_for_project(
        self, organization_id: str, political_project_id: str
    ) -> CampanhaProFactorCache | None:
        return (
            self.db.query(CampanhaProFactorCache)
            .filter(
                CampanhaProFactorCache.organization_id == organization_id,
                CampanhaProFactorCache.political_project_id == political_project_id,
            )
            .order_by(CampanhaProFactorCache.reference_date.desc())
            .first()
        )

    def latest_for_campaign(
        self, organization_id: str, campaign_id: str
    ) -> CampanhaProFactorCache | None:
        return (
            self.db.query(CampanhaProFactorCache)
            .filter(
                CampanhaProFactorCache.organization_id == organization_id,
                CampanhaProFactorCache.campaign_id == campaign_id,
            )
            .order_by(CampanhaProFactorCache.reference_date.desc())
            .first()
        )
