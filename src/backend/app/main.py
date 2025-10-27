from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.celery_app import celery_app

configure_logging()
settings = get_settings()

docs_url = "/docs" if settings.enable_swagger_ui else None
redoc_url = "/redoc" if settings.enable_redoc else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.celery = celery_app
    yield


app = FastAPI(
    title="SOCIALIZER API",
    version="1.1.0",
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=f"/api/{settings.api_version}")


@app.get("/healthz", tags=["health"], include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}
