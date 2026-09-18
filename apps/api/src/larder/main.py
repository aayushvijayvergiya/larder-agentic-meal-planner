"""FastAPI application factory (LLD §2.2)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine

from larder.config import Settings, get_settings
from larder.db.session import init_session_factory
from larder.errors import register_error_handlers
from larder.logging import RequestIdMiddleware, configure_logging
from larder.routers import health

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    app.state.engine = engine
    init_session_factory(engine)
    try:
        yield
    finally:
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Larder API",
        version="1.0.0",
        openapi_url="/openapi.json",
        docs_url="/docs" if settings.app_env != "production" else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    configure_logging(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    for r in (health.router,):
        app.include_router(r, prefix=API_PREFIX)
    return app


app = create_app()
