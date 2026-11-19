from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.version)

    from backend.app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware

    # Added first = innermost. CORS is added last so even 429 responses carry CORS headers.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, chat_per_min=settings.rate_limit_chat_per_min,
                       default_per_min=settings.rate_limit_default_per_min,
                       chat_per_day=settings.rate_limit_chat_per_day_global)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Internal-Token"],
    )

    from backend.app.api.alerts import router as alerts_router
    from backend.app.api.chat import router as chat_router
    from backend.app.api.geo import router as geo_router
    from backend.app.api.risk import router as risk_router
    from backend.app.api.voice import router as voice_router

    app.include_router(chat_router)
    app.include_router(alerts_router)
    app.include_router(risk_router)
    app.include_router(geo_router)
    app.include_router(voice_router)

    @app.get("/health")
    def health() -> dict:
        from backend.app.runtime_data import missing_files

        missing = missing_files(settings.data_dir)
        return {"status": "ok" if not missing else "degraded", "app": settings.app_name,
                "version": settings.version, "missing_data": missing[:10]}

    return app


app = create_app()
