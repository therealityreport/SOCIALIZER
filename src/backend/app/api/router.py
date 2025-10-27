from fastapi import APIRouter

from .routes import alerts, analytics, cast, exports, health, integrity, threads

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(threads.router)
api_router.include_router(cast.router)
api_router.include_router(analytics.router)
api_router.include_router(exports.router)
api_router.include_router(alerts.router)
api_router.include_router(integrity.router)
