"""Async engine and session factory (LLD §2.1)."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from larder.config import get_settings

engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def make_engine(url: str | None = None) -> AsyncEngine:
    return create_async_engine(url or get_settings().database_url, pool_pre_ping=True)


def init_session_factory(eng: AsyncEngine) -> None:
    global engine, async_session_factory
    engine = eng
    async_session_factory = async_sessionmaker(eng, expire_on_commit=False)


def session_factory() -> async_sessionmaker[AsyncSession]:
    if async_session_factory is None:
        raise RuntimeError("session factory not initialised; call init_session_factory() in the app lifespan")
    return async_session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory()() as session:
        yield session
