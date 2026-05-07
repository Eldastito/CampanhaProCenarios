from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.predictions_persisted import router as predictions_router
from app.api.v1.endpoints.scenarios_persisted import router as scenarios_router

router = APIRouter()
router.include_router(health_router, prefix="/health", tags=["health"])
router.include_router(scenarios_router, prefix="/scenarios", tags=["scenarios-v2"])
router.include_router(predictions_router, prefix="/predictions", tags=["predictions-v2"])
