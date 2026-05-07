import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_cors_origins, settings
from app.services.bootstrap_service import BootstrapService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    BootstrapService.initialize()
    logger.info("application_startup", extra={"env": settings.app_env})
    yield
    logger.info("application_shutdown")


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        version="0.3.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    cors_origins = get_cors_origins()
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # ---------------------------------------------------------------------------
    # Global exception handlers
    # ---------------------------------------------------------------------------

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        error_msg = f"{type(exc).__name__}: {exc}"
        logger.error(
            "unhandled_exception",
            extra={"path": request.url.path, "error": error_msg},
            exc_info=exc,
        )
        # In non-production environments surface the real error so devs can see it
        if settings.app_env.lower() != "production":
            detail = f"[{settings.app_env}] {error_msg}"
        else:
            detail = "An unexpected error occurred. Please try again later."
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": detail},
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_application()
