from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.backoffice_ingest import router as backoffice_ingest_router
from app.api.v1.endpoints.campanhapro_ingest import router as campanhapro_ingest_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.dossiers import router as dossiers_router
from app.api.v1.endpoints.graph import router as graph_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.political_agents import router as political_agents_router
from app.api.v1.endpoints.political_evidence import router as political_evidence_router
from app.api.v1.endpoints.political_graph import router as political_graph_router
from app.api.v1.endpoints.political_projects import router as political_projects_router
from app.api.v1.endpoints.predictions import router as predictions_router
from app.api.v1.endpoints.research import router as research_router
from app.api.v1.endpoints.saved_predictions import router as saved_predictions_router
from app.api.v1.endpoints.saved_research import router as saved_research_router
from app.api.v1.endpoints.scenarios import router as scenarios_router
from app.api.v1.endpoints.simulations_graph import router as simulations_router

router = APIRouter()
router.include_router(health_router, prefix="/health", tags=["health"])
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(campanhapro_ingest_router, prefix="/campanhapro", tags=["campanhapro-ingest"])
router.include_router(backoffice_ingest_router, prefix="/backoffice", tags=["backoffice-ingest"])
router.include_router(scenarios_router, prefix="/scenarios", tags=["scenarios"])
router.include_router(political_projects_router, prefix="/political/projects", tags=["political-projects"])
router.include_router(dossiers_router, prefix="/political/projects/{project_id}/dossiers", tags=["dossiers"])
router.include_router(political_evidence_router, prefix="/political", tags=["political-evidence"])
router.include_router(political_graph_router, prefix="/political", tags=["political-graph"])
router.include_router(political_agents_router, prefix="/political", tags=["political-agents"])
router.include_router(predictions_router, prefix="/predictions", tags=["predictions"])
router.include_router(graph_router, prefix="/graph", tags=["graph"])
router.include_router(simulations_router, prefix="/simulations", tags=["simulations"])
router.include_router(saved_predictions_router, prefix="/saved-predictions", tags=["saved-predictions"])
router.include_router(research_router, prefix="/research", tags=["research"])
router.include_router(saved_research_router, prefix="/saved-research", tags=["saved-research"])
router.include_router(chat_router, prefix="/chat", tags=["chat"])
