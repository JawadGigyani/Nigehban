from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from backend.app.api.alerts import router as alerts_router
    from backend.app.api.chat import router as chat_router
    from backend.app.api.risk import router as risk_router

    app.include_router(chat_router)
    app.include_router(alerts_router)
    app.include_router(risk_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name, "version": settings.version}

    return app


app = create_app()
