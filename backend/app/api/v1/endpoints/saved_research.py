"""Saved Research endpoints — persist AI research results."""
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.db.session import get_db
from app.deps.auth import require_scenario_access
from app.models.saved_research import SavedResearch

logger = logging.getLogger(__name__)
router = APIRouter(tags=["saved-research"])


class SaveResearchRequest(BaseModel):
    organization_id: str
    name: str
    candidate_name: str
    party: str
    party_abbreviation: str
    office: str
    search_performed: bool = False
    political_history: str | None = None
    current_mandates: str | None = None
    platform_and_goals: str | None = None
    recent_news: str | None = None
    legal_issues: str | None = None
    ficha_limpa_status: str | None = None
    background: str | None = None
    rejection_profile: dict | None = None
    graph_context_text: str | None = None
    sources: list | None = None
    notes: str | None = None


@router.get("", summary="List saved research results")
def list_saved_research(
    organization_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    items = (
        db.query(SavedResearch)
        .filter(SavedResearch.organization_id == organization_id)
        .order_by(SavedResearch.created_at.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "candidate_name": r.candidate_name,
                "party": r.party,
                "party_abbreviation": r.party_abbreviation,
                "office": r.office,
                "search_performed": r.search_performed,
                "created_at": r.created_at.isoformat(),
            }
            for r in items
        ]
    }


@router.get("/{research_id}", summary="Get a saved research detail")
def get_saved_research(
    research_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    r = db.query(SavedResearch).filter(SavedResearch.id == research_id).first()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    return _serialize(r)


@router.post("", summary="Save a research result")
def save_research(
    body: SaveResearchRequest,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    rec = SavedResearch(
        id=str(uuid4()),
        organization_id=body.organization_id,
        name=body.name,
        candidate_name=body.candidate_name,
        party=body.party,
        party_abbreviation=body.party_abbreviation,
        office=body.office,
        search_performed=body.search_performed,
        political_history=body.political_history,
        current_mandates=body.current_mandates,
        platform_and_goals=body.platform_and_goals,
        recent_news=body.recent_news,
        legal_issues=body.legal_issues,
        ficha_limpa_status=body.ficha_limpa_status,
        background=body.background,
        rejection_profile=body.rejection_profile,
        graph_context_text=body.graph_context_text,
        sources=body.sources,
        notes=body.notes,
        created_at=utc_now_naive(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _serialize(rec)


@router.delete("/{research_id}", summary="Delete a saved research result")
def delete_saved_research(
    research_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    r = db.query(SavedResearch).filter(SavedResearch.id == research_id).first()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    db.delete(r)
    db.commit()
    return {"deleted": research_id}


def _serialize(r: SavedResearch) -> dict:
    return {
        "id": r.id,
        "organization_id": r.organization_id,
        "name": r.name,
        "candidate_name": r.candidate_name,
        "party": r.party,
        "party_abbreviation": r.party_abbreviation,
        "office": r.office,
        "search_performed": r.search_performed,
        "political_history": r.political_history,
        "current_mandates": r.current_mandates,
        "platform_and_goals": r.platform_and_goals,
        "recent_news": r.recent_news,
        "legal_issues": r.legal_issues,
        "ficha_limpa_status": r.ficha_limpa_status,
        "background": r.background,
        "rejection_profile": r.rejection_profile,
        "graph_context_text": r.graph_context_text,
        "sources": r.sources,
        "notes": r.notes,
        "created_at": r.created_at.isoformat(),
    }
