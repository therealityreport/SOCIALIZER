from fastapi import APIRouter

from .routes import alerts, analytics, cast, episode_discussions, exports, health, instagram, integrity, llm, threads

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(threads.router)
api_router.include_router(cast.router)
api_router.include_router(analytics.router)
api_router.include_router(exports.router)
api_router.include_router(alerts.router)
api_router.include_router(integrity.router)
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(episode_discussions.router)
api_router.include_router(instagram.router)
