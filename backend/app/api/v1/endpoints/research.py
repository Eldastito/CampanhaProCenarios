"""AI Research Agent endpoints — researches political candidates via OpenAI web search."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.deps.auth import require_scenario_access
from app.services.research_service import ResearchService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["research"])


class ResearchCandidateRequest(BaseModel):
    name: str
    party: str
    party_abbreviation: str
    office: str


class CompareRejectionRequest(BaseModel):
    candidates: list[ResearchCandidateRequest]


@router.post("/candidate", summary="Research a political candidate via AI + web search")
def research_candidate(body: ResearchCandidateRequest, _=Depends(require_scenario_access)) -> dict:
    try:
        svc = ResearchService()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    try:
        result = svc.research_candidate(
            name=body.name,
            party=body.party,
            office=body.office,
            party_abbreviation=body.party_abbreviation,
        )
    except Exception as exc:
        logger.error("research_candidate_error", extra={"error": str(exc)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return result


@router.post("/compare", summary="Compare rejection profiles of multiple candidates")
def compare_rejection(body: CompareRejectionRequest, _=Depends(require_scenario_access)) -> dict:
    if len(body.candidates) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="São necessários pelo menos 2 candidatos para comparação.",
        )
    if len(body.candidates) > 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Máximo de 5 candidatos por comparação.",
        )

    try:
        svc = ResearchService()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    try:
        result = svc.compare_rejection(
            candidates=[c.model_dump() for c in body.candidates]
        )
    except Exception as exc:
        logger.error("compare_rejection_error", extra={"error": str(exc)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return result
