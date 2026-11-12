import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.datasets import router as datasets_router
from app.api.routes.engines import router as engines_router
from app.api.routes.evaluations import router as evaluations_router
from app.api.routes.experiments import router as experiments_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.models import router as models_router
from app.api.routes.predictions import router as predictions_router
from app.core.config import get_settings
from app.core.logging import configure_logging, request_id_context

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.services.job_service import recover_local_jobs

    recover_local_jobs()
    yield


app = FastAPI(
    title=settings.app_name, version="0.3.0", openapi_url="/api/v1/openapi.json", lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Request-ID", "Idempotency-Key"],
)


@app.middleware("http")
async def correlation_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_context.set(request_id)
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            },
        )
        return response
    finally:
        request_id_context.reset(token)


app.include_router(health_router, prefix="/api/v1")
app.include_router(datasets_router, prefix="/api/v1")
app.include_router(engines_router, prefix="/api/v1")
app.include_router(experiments_router, prefix="/api/v1")
app.include_router(models_router, prefix="/api/v1")
app.include_router(predictions_router, prefix="/api/v1")
app.include_router(evaluations_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
