"""FastAPI application factory (LLD §2.2)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.ext.asyncio import create_async_engine

from larder.agents.onboarding.graph import build_onboarding_graph
from larder.config import Settings, get_settings
from larder.db.session import init_session_factory
from larder.errors import register_error_handlers
from larder.llm.factory import get_llm
from larder.logging import RequestIdMiddleware, configure_logging
from larder.routers import health, households, me, meals, onboarding, pantry, plans
from larder.services.plans import enqueue_first_plan

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    app.state.engine = engine
    init_session_factory(engine)
    pool = AsyncConnectionPool(
        settings.checkpoint_database_url,
        min_size=1,
        max_size=5,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    await pool.open()
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()
    app.state.checkpointer = checkpointer
    app.state.onboarding_graph = build_onboarding_graph(checkpointer)
    try:
        yield
    finally:
        await pool.close()
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
    app.state.llm = get_llm(settings)
    app.state.first_plan_hook = enqueue_first_plan
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
    for r in (
        health.router,
        me.router,
        onboarding.router,
        households.router,
        pantry.router,
        meals.router,
        plans.router,
    ):
        app.include_router(r, prefix=API_PREFIX)
    return app


app = create_app()
