import os
import subprocess
import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AUTH_MODE", "hs256")
TEST_JWT_SECRET = "test-secret-with-at-least-thirty-two-bytes"
os.environ.setdefault("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("SCHEDULER_SECRET", "test-scheduler")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/larder_test"),
)

from larder.config import get_settings  # noqa: E402
from larder.db import session as db_session_module  # noqa: E402
from larder.main import create_app  # noqa: E402

API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ALL_TABLES = (
    "profiles, households, household_members, household_invites, pantry_items, meals, meal_ingredients, "
    "meal_plans, plan_entries, plan_entry_variations, plan_jobs, meal_feedback, refresh_runs"
)


@pytest.fixture(scope="session", autouse=True)
def migrate():
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True, cwd=API_DIR)


@pytest.fixture
async def client():
    get_settings.cache_clear()
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c


@pytest.fixture
def fake_llm(client):
    """The app's FakeLLM instance, for scripting responses and inspecting recorded calls."""
    llm = client._transport.app.state.llm
    llm.reset()
    return llm


@pytest.fixture
async def db_session(client):
    async with db_session_module.session_factory()() as s:
        yield s
        await s.rollback()


@pytest.fixture(autouse=True)
async def truncate(client):
    yield
    async with db_session_module.session_factory()() as s:
        await s.execute(text(f"truncate {ALL_TABLES} cascade"))
        await s.commit()


def auth_headers(user_id: uuid.UUID, email: str = "u@example.com") -> dict[str, str]:
    import jwt

    token = jwt.encode(
        {"sub": str(user_id), "email": email, "aud": "authenticated"}, TEST_JWT_SECRET, algorithm="HS256"
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_user_complete(db_session):
    """Creates a profile with a completed onboarding plus its implicit household.

    Returns SimpleNamespace(profile, household, headers).
    """

    async def _make(display_name: str = "Priya", diet_type: str = "vegetarian", allergens: list[str] | None = None):
        from larder.db.models import DEFAULT_SLOTS, Household, HouseholdMember, Profile

        p = Profile(
            id=uuid.uuid4(),
            email=f"{display_name.lower()}-{uuid.uuid4().hex[:6]}@example.com",
            display_name=display_name,
            diet_type=diet_type,
            allergens=allergens or [],
            onboarding_status="complete",
            max_prep_minutes=45,
            cuisines=["north_indian"],
        )
        db_session.add(p)
        await db_session.flush()
        h = Household(name=f"{display_name}'s kitchen", owner_id=p.id, is_implicit=True, slots=list(DEFAULT_SLOTS))
        db_session.add(h)
        await db_session.flush()
        db_session.add(HouseholdMember(household_id=h.id, user_id=p.id, role="owner", preferred_view="single"))
        await db_session.commit()
        return SimpleNamespace(profile=p, household=h, headers=auth_headers(p.id, p.email))

    return _make
