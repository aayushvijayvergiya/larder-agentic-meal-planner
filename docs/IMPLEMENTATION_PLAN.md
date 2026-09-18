# Larder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Larder, a pantry-first agentic meal planner with a FastAPI + LangGraph backend, a Next.js web app and an Expo mobile app, deployable to Render, Vercel and Supabase.

**Architecture:** One FastAPI service owns all business logic and the LangGraph agents (onboarding, planner, enrichment, categoriser) and talks to Supabase Postgres; Supabase Auth issues JWTs that both clients pass as Bearer tokens. A Render cron tick drives weekly and daily plan refreshes. Web and mobile share a generated OpenAPI client with TanStack Query hooks and a design-tokens package.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async + asyncpg, Alembic, Pydantic v2, LangGraph + langgraph-checkpoint-postgres, langchain-groq, pytest; Node 22, pnpm 10, Turborepo, Next.js (App Router), Tailwind CSS 4, Expo + Expo Router, TanStack Query 5, openapi-typescript + openapi-fetch, Vitest, Playwright, jest-expo.

**Spec:** `docs/LLD.md` is the contract for every name, column, endpoint, prompt and screen referenced below; `docs/HLD.md` explains the why. Executors read both. When a task says "per LLD §X", copy the definition from that section exactly.

## Global Constraints

- Package name `larder`; API base path `/api/v1`; error envelope `{"error": {"code","message","details"}}` (LLD §2.3).
- Python 3.12; Node 22; pnpm 10. Never use npm or yarn. Python deps only via `uv add`.
- `LLM_PROVIDER=fake` must make every feature work with no network; tests never call the real LLM.
- Routers contain no business logic; services own transactions; agents never import routers (LLD §2.1).
- All ingredient and pantry names stored with `normalized_name = normalize_name(name)` (LLD §7.1).
- Hard constraints (allergens, diet compatibility, hard medical rules) are enforced in code, never only in prompts (LLD §8.2).
- Frontend visual rules LLD §9.2 are mandatory: one accent (`#B4532A` light / `#E07A4B` dark), Fraunces headings, Instrument Sans body, no gradients, lists over card grids, Lucide icons.
- Every task ends with tests passing and a commit. Commit messages use conventional prefixes (`feat:`, `test:`, `chore:`).
- Windows host: use forward slashes in scripts and `uv run` / `pnpm` wrappers rather than activating venvs.

---

# Phase 0 — Repository bootstrap

### Task 1: Monorepo skeleton

**Files:**
- Create: `package.json`, `pnpm-workspace.yaml`, `turbo.json`, `.gitignore`, `.editorconfig`, `.nvmrc`, `README.md`, `.env.example`
- Create: `apps/.gitkeep`, `packages/.gitkeep`

**Interfaces:**
- Produces: root scripts `dev`, `build`, `lint`, `typecheck`, `test`, `gen`, `api`, `api:test` (LLD §1).

- [x] **Step 1: Initialise git and workspace files**

```bash
git init -b main
```

`package.json`:
```json
{
  "name": "larder",
  "private": true,
  "packageManager": "pnpm@10.0.0",
  "engines": { "node": ">=22" },
  "scripts": {
    "dev": "turbo run dev",
    "build": "turbo run build",
    "lint": "turbo run lint",
    "typecheck": "turbo run typecheck",
    "test": "turbo run test",
    "gen": "pnpm --filter @larder/api-client gen",
    "api": "cd apps/api && uv run uvicorn larder.main:app --reload --port 8000",
    "api:test": "cd apps/api && uv run pytest -q"
  },
  "devDependencies": { "turbo": "^2.3.0", "typescript": "^5.6.0" }
}
```
`pnpm-workspace.yaml`:
```yaml
packages:
  - "apps/*"
  - "packages/*"
```
`turbo.json`:
```json
{
  "$schema": "https://turbo.build/schema.json",
  "tasks": {
    "build": { "dependsOn": ["^build"], "outputs": [".next/**", "!.next/cache/**", "dist/**"] },
    "dev": { "cache": false, "persistent": true },
    "lint": {},
    "typecheck": { "dependsOn": ["^build"] },
    "test": { "dependsOn": ["^build"] }
  }
}
```
`.gitignore`: `node_modules/`, `.next/`, `dist/`, `.turbo/`, `.env`, `.env.*.local`, `apps/api/.venv/`, `__pycache__/`, `.pytest_cache/`, `.expo/`, `coverage/`, `playwright-report/`, `test-results/`.
`.nvmrc`: `22`. `.env.example`: copy verbatim from LLD §11. `README.md`: title, one-paragraph description, "Run locally" (Docker Postgres, `pnpm api`, `pnpm dev`), links to the three docs.

- [x] **Step 2: Install and verify**

Run: `pnpm install` → creates `pnpm-lock.yaml`. Run: `pnpm turbo --version` → prints a 2.x version.

- [x] **Step 3: Commit**

```bash
git add -A && git commit -m "chore: bootstrap monorepo workspace"
```

---

### Task 2: API project skeleton with settings and health endpoint

**Files:**
- Create: `apps/api/pyproject.toml`, `apps/api/src/larder/__init__.py`, `apps/api/src/larder/config.py`, `apps/api/src/larder/main.py`, `apps/api/src/larder/routers/__init__.py`, `apps/api/src/larder/routers/health.py`, `apps/api/tests/__init__.py`, `apps/api/tests/conftest.py`, `apps/api/tests/integration/test_health.py`

**Interfaces:**
- Produces: `get_settings() -> Settings` with every variable in LLD §2.4; `create_app(settings=None) -> FastAPI`; `GET /api/v1/health`.

- [x] **Step 1: Create the project**

```bash
cd apps/api
uv init --name larder --package --python 3.12
uv add fastapi "uvicorn[standard]" pydantic pydantic-settings sqlalchemy asyncpg alembic "psycopg[binary,pool]" pyjwt[crypto] httpx langgraph langgraph-checkpoint-postgres langchain-groq python-json-logger
uv add --dev pytest pytest-asyncio ruff mypy
```
In `pyproject.toml` add:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
[tool.ruff]
line-length = 120
target-version = "py312"
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

- [x] **Step 2: Write the failing health test**

`tests/conftest.py` (initial version; extended in Task 3):
```python
import os
import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AUTH_MODE", "hs256")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("SCHEDULER_SECRET", "test-scheduler")
os.environ.setdefault("DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/larder_test"))

from larder.config import get_settings  # noqa: E402
from larder.main import create_app  # noqa: E402

@pytest.fixture
async def client():
    get_settings.cache_clear()
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
```
`tests/integration/test_health.py`:
```python
async def test_health_reports_provider(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["llm_provider"] == "fake"
```

- [x] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_health.py -v` → FAIL (`ModuleNotFoundError: larder.config`).

- [x] **Step 4: Implement settings, app factory and health**

`src/larder/config.py`:
```python
from functools import lru_cache
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: Literal["local", "test", "production"] = "local"
    database_url: str
    checkpoint_database_url: str | None = None
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    auth_mode: Literal["jwks", "hs256"] = "jwks"
    jwt_audience: str = "authenticated"
    llm_provider: Literal["groq", "fake"] | None = None
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
    llm_timeout_seconds: int = 60
    scheduler_secret: str = ""
    cors_origins: str = "http://localhost:3000"
    plan_history_weeks: int = 8

    @model_validator(mode="after")
    def _defaults(self):
        if self.llm_provider is None:
            self.llm_provider = "groq" if self.groq_api_key else "fake"
        if self.checkpoint_database_url is None:
            self.checkpoint_database_url = self.database_url.replace("postgresql+asyncpg://", "postgresql://")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()
```
`src/larder/routers/health.py`:
```python
from fastapi import APIRouter, Request
from sqlalchemy import text
router = APIRouter(tags=["health"])

@router.get("/health")
async def health(request: Request):
    settings = request.app.state.settings
    db = "ok"
    try:
        async with request.app.state.engine.connect() as conn:
            await conn.execute(text("select 1"))
    except Exception:  # noqa: BLE001
        db = "error"
    body = {"status": "ok" if db == "ok" else "degraded", "database": db, "llm_provider": settings.llm_provider}
    return body if db == "ok" else JSONResponse(body, status_code=503)
```
`src/larder/main.py`: `create_app` per LLD §2.2 with only `health.router` for now; `lifespan` creates `app.state.engine = create_async_engine(settings.database_url)` and disposes it on shutdown; `app.state.settings = settings`.

- [x] **Step 5: Start a test database and run the test**

Run: `docker run -d --name larder-test-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=larder_test -p 5433:5432 postgres:16`
Run: `uv run pytest tests/integration/test_health.py -v` → PASS.

- [x] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(api): project skeleton with settings and health endpoint"
```

---

# Phase 1 — API foundation

### Task 3: Database models, Alembic migration and test fixtures

**Files:**
- Create: `apps/api/src/larder/db/__init__.py`, `db/session.py`, `db/base.py`, `db/models/__init__.py`, `db/models/profile.py`, `db/models/household.py`, `db/models/pantry.py`, `db/models/meal.py`, `db/models/plan.py`, `db/models/feedback.py`, `db/models/refresh.py`
- Create: `apps/api/alembic.ini`, `apps/api/alembic/env.py`, `apps/api/alembic/script.py.mako`, `apps/api/alembic/versions/0001_initial.py`
- Modify: `apps/api/tests/conftest.py`
- Test: `apps/api/tests/integration/test_schema.py`

**Interfaces:**
- Produces: ORM classes `Profile, Household, HouseholdMember, HouseholdInvite, PantryItem, Meal, MealIngredient, MealPlan, PlanEntry, PlanEntryVariation, PlanJob, MealFeedback, RefreshRun` with columns exactly as LLD §3.2; Python enums in `db/models/enums.py` named as LLD §3.1; `get_session()` dependency yielding `AsyncSession`; `async_session_factory`.

- [x] **Step 1: Write the failing schema test**

```python
# tests/integration/test_schema.py
from sqlalchemy import text

async def test_all_tables_exist(db_session):
    rows = await db_session.execute(text("select table_name from information_schema.tables where table_schema='public'"))
    names = {r[0] for r in rows}
    expected = {"profiles","households","household_members","household_invites","pantry_items","meals","meal_ingredients",
                "meal_plans","plan_entries","plan_entry_variations","plan_jobs","meal_feedback","refresh_runs"}
    assert expected <= names

async def test_one_household_per_user(db_session, make_user_complete):
    from larder.db.models import HouseholdMember, Household
    user = await make_user_complete()
    other = Household(name="x", owner_id=user.profile.id, timezone="Asia/Kolkata", slots=[{"key":"dinner","label":"Dinner","order":1}])
    db_session.add(other); await db_session.flush()
    db_session.add(HouseholdMember(household_id=other.id, user_id=user.profile.id, role="member"))
    import pytest, sqlalchemy.exc
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await db_session.flush()
```

- [x] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/integration/test_schema.py -v` → FAIL (fixture `db_session` not found).

- [x] **Step 3: Implement base, session and models**

`db/base.py`:
```python
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase): pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)
```
`db/session.py`:
```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from larder.config import get_settings

def make_engine(url: str | None = None):
    return create_async_engine(url or get_settings().database_url, pool_pre_ping=True)

engine = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None

def init_session_factory(eng):
    global engine, async_session_factory
    engine = eng
    async_session_factory = async_sessionmaker(eng, expire_on_commit=False)

async def get_session():
    async with async_session_factory() as session:
        yield session
```
Models: one file per LLD §3.2 group, using `sqlalchemy.Enum(..., name="<enum name>")`, `ARRAY(Text)`, `JSONB`, `UUID(as_uuid=True)`, `server_default=text("gen_random_uuid()")`. Add the unique constraints and indexes listed in LLD §3.2. `db/models/__init__.py` re-exports everything.

Example (`db/models/household.py`, abbreviated to show the pattern; write all columns):
```python
class Household(Base, TimestampMixin):
    __tablename__ = "households"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str]
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"), nullable=False)
    timezone: Mapped[str] = mapped_column(default="Asia/Kolkata")
    slots: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    weekly_refresh_day: Mapped[int] = mapped_column(SmallInteger, default=6)
    weekly_refresh_time: Mapped[time] = mapped_column(Time, default=time(18, 0))
    daily_refresh_time: Mapped[time] = mapped_column(Time, default=time(6, 0))
    is_implicit: Mapped[bool] = mapped_column(default=False)
    members: Mapped[list["HouseholdMember"]] = relationship(back_populates="household", cascade="all, delete-orphan")

class HouseholdMember(Base):
    __tablename__ = "household_members"
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True, unique=True)
    role: Mapped[str] = mapped_column(Enum("owner", "member", name="member_role_enum"), nullable=False)
    preferred_view: Mapped[str] = mapped_column(Enum("single", "family", name="view_enum"), default="family", nullable=False)
    joined_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

- [x] **Step 4: Alembic**

Run: `uv run alembic init -t async alembic`. Edit `alembic/env.py`: `target_metadata = Base.metadata`; read URL from `get_settings().database_url`; add
```python
def include_object(obj, name, type_, reflected, compare_to):
    return not (type_ == "table" and name.startswith("checkpoint"))
```
and pass `include_object=include_object` to `context.configure`. Generate: `uv run alembic revision --autogenerate -m "initial"` → rename to `0001_initial.py`; verify it creates all enums and tables; add `op.execute("create extension if not exists pgcrypto")` at the top of `upgrade()` (for `gen_random_uuid` on older Postgres).

- [x] **Step 5: Extend conftest**

Add to `tests/conftest.py`:
```python
import subprocess, uuid
from sqlalchemy import text
from larder.db.session import make_engine, init_session_factory, async_session_factory

@pytest.fixture(scope="session", autouse=True)
def migrate():
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True, cwd=os.path.dirname(os.path.dirname(__file__)))

@pytest.fixture
async def db_session(client):
    async with async_session_factory() as s:
        yield s
        await s.rollback()

@pytest.fixture(autouse=True)
async def truncate(client):
    yield
    async with async_session_factory() as s:
        await s.execute(text("truncate profiles, households, household_members, household_invites, pantry_items, meals, meal_ingredients, "
                             "meal_plans, plan_entries, plan_entry_variations, plan_jobs, meal_feedback, refresh_runs cascade"))
        await s.commit()

def auth_headers(user_id: uuid.UUID, email: str = "u@example.com") -> dict:
    import jwt
    token = jwt.encode({"sub": str(user_id), "email": email, "aud": "authenticated"}, "test-secret", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def make_user_complete(db_session):
    """Creates profile + implicit household; returns SimpleNamespace(profile, household, headers)."""
    async def _make(display_name="Priya", diet_type="vegetarian", allergens=None):
        from larder.db.models import Profile, Household, HouseholdMember
        p = Profile(id=uuid.uuid4(), email=f"{display_name.lower()}-{uuid.uuid4().hex[:6]}@example.com", display_name=display_name,
                    diet_type=diet_type, allergens=allergens or [], onboarding_status="complete", max_prep_minutes=45, cuisines=["north_indian"])
        db_session.add(p); await db_session.flush()
        h = Household(name=f"{display_name}'s kitchen", owner_id=p.id, is_implicit=True,
                      slots=[{"key":"breakfast","label":"Breakfast","order":1},{"key":"lunch","label":"Lunch","order":2},
                             {"key":"snack","label":"Snack","order":3},{"key":"dinner","label":"Dinner","order":4}])
        db_session.add(h); await db_session.flush()
        db_session.add(HouseholdMember(household_id=h.id, user_id=p.id, role="owner", preferred_view="single"))
        await db_session.commit()
        from types import SimpleNamespace
        return SimpleNamespace(profile=p, household=h, headers=auth_headers(p.id, p.email))
    return _make
```
Wire `lifespan` in `main.py` to call `init_session_factory(engine)`.

- [x] **Step 6: Run tests**

Run: `uv run pytest -v` → PASS (health + schema).

- [x] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(api): database models, initial migration and test fixtures"
```

---

### Task 4: Error envelope and request logging

**Files:**
- Create: `apps/api/src/larder/errors.py`, `apps/api/src/larder/logging.py`
- Modify: `apps/api/src/larder/main.py`
- Test: `apps/api/tests/integration/test_errors.py`

**Interfaces:**
- Produces: `class ApiError(Exception): def __init__(self, code: str, status: int, message: str, details: dict | None = None)`; helper constructors `not_found(msg)`, `forbidden(msg)`, `conflict(msg)`, `validation(msg, field=None)`, `unauthorized()`; `register_error_handlers(app)`; `RequestIdMiddleware` adding `X-Request-Id`.

- [x] **Step 1: Write failing tests**

```python
async def test_validation_error_envelope(client):
    r = await client.get("/api/v1/health?x=")  # health ignores params; use a temp route instead
```
Instead, register a throwaway route inside the test:
```python
from larder.errors import ApiError

async def test_api_error_envelope(client):
    app = client._transport.app
    @app.get("/boom")
    async def boom(): raise ApiError("conflict", 409, "already there", {"field": "name"})
    r = await client.get("/boom")
    assert r.status_code == 409
    assert r.json() == {"error": {"code": "conflict", "message": "already there", "details": {"field": "name"}}}
    assert "x-request-id" in r.headers

async def test_request_validation_envelope(client):
    app = client._transport.app
    from pydantic import BaseModel
    class In(BaseModel): n: int
    @app.post("/echo")
    async def echo(body: In): return body
    r = await client.post("/echo", json={"n": "x"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
```

- [x] **Step 2: Run to verify failure** → FAIL (`larder.errors` missing).

- [x] **Step 3: Implement** `errors.py` (handlers for `ApiError`, `RequestValidationError` → 422 envelope with `details={"errors": exc.errors()}`, generic `Exception` → 500 `internal_error` with logging) and `logging.py` (JSON formatter with `request_id`, `user_id` from `request.state` when set; middleware generating `uuid4` request ids). Register both in `create_app`.

- [x] **Step 4: Run tests** → PASS. **Step 5: Commit** `feat(api): error envelope and request logging`.

---

### Task 5: Supabase JWT auth, JIT profile provisioning, `/me`

**Files:**
- Create: `apps/api/src/larder/auth/__init__.py`, `auth/jwt.py`, `auth/deps.py`, `services/profiles.py`, `schemas/common.py`, `schemas/me.py`, `routers/me.py`
- Modify: `main.py` (include router)
- Test: `tests/integration/test_auth.py`, `tests/integration/test_me.py`

**Interfaces:**
- Consumes: models from Task 3, `ApiError` from Task 4.
- Produces: `verify_token(token, settings) -> TokenClaims`; `CurrentUser` dataclass; dependencies `get_current_user`, `require_household`, `require_owner` (LLD §4.2); `ProfileOut`, `ProfilePatch`, `HouseholdOut`, `MemberSummary`, `SlotDef` (LLD §6.1, §6.3); `profiles.get_or_create_profile(session, claims) -> Profile`; `profiles.update_profile(session, profile, patch) -> Profile`.

- [x] **Step 1: Write failing tests**

```python
# tests/integration/test_auth.py
from tests.conftest import auth_headers
import uuid

async def test_missing_token_401(client):
    r = await client.get("/api/v1/me"); assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"

async def test_bad_token_401(client):
    r = await client.get("/api/v1/me", headers={"Authorization": "Bearer nope"}); assert r.status_code == 401

async def test_first_call_provisions_profile(client):
    uid = uuid.uuid4()
    r = await client.get("/api/v1/me", headers=auth_headers(uid, "new@example.com"))
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["id"] == str(uid) and body["household"] is None and body["onboarding_status"] == "pending"

# tests/integration/test_me.py
async def test_patch_me_updates_fields(client, make_user_complete):
    u = await make_user_complete()
    r = await client.patch("/api/v1/me", json={"height_cm": 172, "dislikes": ["Bitter Gourd"]}, headers=u.headers)
    assert r.status_code == 200 and r.json()["height_cm"] == 172 and r.json()["dislikes"] == ["bitter gourd"]

async def test_patch_me_rejects_out_of_range(client, make_user_complete):
    u = await make_user_complete()
    r = await client.patch("/api/v1/me", json={"height_cm": 900}, headers=u.headers)
    assert r.status_code == 422
```

- [x] **Step 2: Run to verify failure** → FAIL (404 on `/me`).

- [x] **Step 3: Implement**

`auth/jwt.py` exactly as LLD §4.1. `auth/deps.py`:
```python
async def get_current_user(request: Request, session: AsyncSession = Depends(get_session)) -> CurrentUser:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "): raise unauthorized()
    claims = verify_token(auth[7:], request.app.state.settings)
    profile = await get_or_create_profile(session, claims)
    membership = await session.scalar(select(HouseholdMember).where(HouseholdMember.user_id == profile.id))
    household = await session.get(Household, membership.household_id, options=[selectinload(Household.members)]) if membership else None
    request.state.user_id = str(profile.id)
    return CurrentUser(profile=profile, household=household, membership=membership)
```
`ProfilePatch` fields with validators: `height_cm: int | None = Field(None, ge=50, le=250)`, `weight_kg: float | None = Field(None, ge=20, le=400)`, `max_prep_minutes: int | None = Field(None, ge=5, le=240)`, list fields normalised with `normalize_name` (create `services/normalize.py` now with just `normalize_name` per LLD §7.1; Task 8 completes it), `medical_conditions: list[MedicalCondition]` with `name` and optional `notes`. `HouseholdOut.from_model(household)` builds `members` with display names via the loaded relationship (`HouseholdMember.profile` relationship).

- [x] **Step 4: Run tests** → PASS. **Step 5: Commit** `feat(api): supabase jwt auth and /me endpoints`.

---

### Task 6: LLM provider layer (protocol, fake, Groq)

**Files:**
- Create: `apps/api/src/larder/llm/__init__.py`, `llm/base.py`, `llm/fake.py`, `llm/groq.py`, `llm/factory.py`
- Modify: `main.py` (`app.state.llm = get_llm(settings)`), `tests/conftest.py` (`fake_llm` fixture returning `client._transport.app.state.llm`)
- Test: `tests/unit/test_fake_llm.py`, `tests/unit/test_groq_llm.py`

**Interfaces:**
- Produces: `LLM` protocol, `LLMError`, `FakeLLM` with `script_text(list[str])`, `script_structured(schema, list[BaseModel])`, `fail_next(exc)`, `register_handler(schema_name, fn)`, `calls: list[dict]` (recorded prompts); `GroqLLM(settings)`; `get_llm(settings) -> LLM`; helper `extract_context(user_prompt) -> dict` parsing the `<context>` JSON block (LLD §5).

- [x] **Step 1: Write failing tests**

```python
# tests/unit/test_fake_llm.py
from pydantic import BaseModel
from larder.llm.fake import FakeLLM
from larder.llm.base import LLMError
import pytest

class Out(BaseModel): x: int

async def test_scripted_structured_and_default_text():
    llm = FakeLLM()
    llm.script_structured(Out, [Out(x=7)])
    assert (await llm.complete_structured(system="s", user="u", schema=Out)).x == 7
    assert (await llm.complete_text(system="s", user="hello")).startswith("[fake]")

async def test_fail_next_raises_once():
    llm = FakeLLM(); llm.fail_next(LLMError("down"))
    with pytest.raises(LLMError): await llm.complete_text(system="s", user="u")
    assert (await llm.complete_text(system="s", user="u")).startswith("[fake]")

async def test_unknown_schema_without_handler_raises():
    llm = FakeLLM()
    with pytest.raises(LLMError): await llm.complete_structured(system="s", user="u", schema=Out)

# tests/unit/test_groq_llm.py
def test_factory_picks_fake_without_key(monkeypatch):
    from larder.config import Settings
    from larder.llm.factory import get_llm
    s = Settings(database_url="postgresql+asyncpg://x", groq_api_key="")
    assert get_llm(s).name == "fake"

def test_factory_picks_groq_with_key():
    from larder.config import Settings
    from larder.llm.factory import get_llm
    s = Settings(database_url="postgresql+asyncpg://x", groq_api_key="k")
    assert get_llm(s).name == "groq:openai/gpt-oss-120b"
```

- [x] **Step 2: Run to verify failure** → FAIL.

- [x] **Step 3: Implement**

`llm/base.py` per LLD §5.1 plus:
```python
def extract_context(user: str) -> dict:
    m = re.search(r"<context>(.*?)</context>", user, re.S)
    return json.loads(m.group(1)) if m else {}
```
`llm/fake.py`: class with `_text_queue`, `_structured_queues: dict[str, list]`, `_handlers: dict[str, Callable[[dict, type], BaseModel]]`, `_fail: Exception | None`, `calls`. Order: fail → scripted → handler → `LLMError("no fake handler for X")`. Built-in handlers are registered by later tasks (each agent task adds `register_default_handlers` entries in `llm/fake_handlers.py`, created in Task 10).
`llm/groq.py`:
```python
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

class GroqLLM:
    def __init__(self, settings: Settings):
        self.name = f"groq:{settings.groq_model}"
        self._chat = ChatGroq(model=settings.groq_model, api_key=settings.groq_api_key, base_url=settings.groq_base_url,
                                timeout=settings.llm_timeout_seconds, max_retries=1)
    async def complete_text(self, *, system, user, temperature=0.7) -> str:
        try:
            msg = await self._chat.bind(temperature=temperature).ainvoke([SystemMessage(system), HumanMessage(user)])
            return msg.content if isinstance(msg.content, str) else str(msg.content)
        except Exception as e: raise LLMError(str(e)) from e
    async def complete_structured(self, *, system, user, schema, temperature=0.2):
        for method in ("json_schema", "function_calling"):
            try:
                model = self._chat.bind(temperature=temperature).with_structured_output(schema, method=method)
                out = await model.ainvoke([SystemMessage(system), HumanMessage(user)])
                return out if isinstance(out, schema) else schema.model_validate(out)
            except ValidationError as e: raise LLMError(f"invalid structured output: {e}") from e
            except Exception as e:  # noqa: BLE001
                last = e; continue
        raise LLMError(str(last))
```

- [x] **Step 4: Run** `uv run pytest tests/unit -v` → PASS. **Step 5: Commit** `feat(api): llm provider layer with fake and groq implementations`.

---

# Phase 2 — Households

### Task 7: Households service and router

**Files:**
- Create: `services/households.py`, `schemas/households.py`, `routers/households.py`
- Modify: `main.py`
- Test: `tests/integration/test_households.py`, `tests/unit/test_active_scopes.py`

**Interfaces:**
- Produces: `create_implicit_household(session, profile) -> Household`; `generate_invite(session, household, created_by, expires_in_days=7, max_uses=10) -> HouseholdInvite`; `join_by_code(session, user: CurrentUser, code) -> Household`; `remove_member(session, actor: CurrentUser, household_id, user_id) -> Household | None` (returns the removed user's new implicit household); `set_preferred_view(session, user, view)`; `update_household(session, household, patch)`; `active_scopes(household) -> list[tuple[str, UUID | None]]` (LLD §7.5); endpoints LLD §6.5. Plan generation does not exist yet at this point: `remove_member` returns the removed user's new implicit household, and the router only returns 204. Task 18 modifies this router to call `plans.request_generation` for that household.

- [x] **Step 1: Write failing tests**

```python
# tests/unit/test_active_scopes.py
from types import SimpleNamespace as NS
from larder.services.households import active_scopes

def test_solo_household_is_single():
    h = NS(members=[NS(user_id="a", preferred_view="single")])
    assert active_scopes(h) == [("single", "a")]

def test_family_and_singles():
    h = NS(members=[NS(user_id="a", preferred_view="family"), NS(user_id="b", preferred_view="single")])
    assert active_scopes(h) == [("family", None), ("single", "b")]

# tests/integration/test_households.py
async def test_owner_creates_invite_and_member_joins(client, make_user_complete):
    owner = await make_user_complete("Priya"); joiner = await make_user_complete("Aarav")
    r = await client.post(f"/api/v1/households/{owner.household.id}/invites", json={}, headers=owner.headers)
    assert r.status_code == 201 and len(r.json()["code"]) == 8
    code = r.json()["code"]
    r = await client.post("/api/v1/households/join", json={"code": code}, headers=joiner.headers)
    assert r.status_code == 200
    ids = {m["user_id"] for m in r.json()["members"]}
    assert ids == {str(owner.profile.id), str(joiner.profile.id)}
    r = await client.get("/api/v1/households/me", headers=joiner.headers)
    assert r.json()["id"] == str(owner.household.id)          # implicit household replaced

async def test_member_cannot_create_invite(client, make_user_complete):
    owner = await make_user_complete("Priya"); other = await make_user_complete("Aarav")
    r = await client.post(f"/api/v1/households/{owner.household.id}/invites", json={}, headers=other.headers)
    assert r.status_code == 404   # wrong household => not found, never leak

async def test_expired_code_conflicts(client, make_user_complete, db_session):
    owner = await make_user_complete("Priya"); joiner = await make_user_complete("Aarav")
    from larder.services.households import generate_invite
    inv = await generate_invite(db_session, owner.household, owner.profile.id, expires_in_days=-1); await db_session.commit()
    r = await client.post("/api/v1/households/join", json={"code": inv.code}, headers=joiner.headers)
    assert r.status_code == 409

async def test_remove_member_gives_new_implicit_household(client, make_user_complete, db_session):
    owner = await make_user_complete("Priya"); joiner = await make_user_complete("Aarav")
    from larder.services.households import generate_invite
    inv = await generate_invite(db_session, owner.household, owner.profile.id); await db_session.commit()
    await client.post("/api/v1/households/join", json={"code": inv.code}, headers=joiner.headers)
    r = await client.delete(f"/api/v1/households/{owner.household.id}/members/{joiner.profile.id}", headers=owner.headers)
    assert r.status_code == 204
    r = await client.get("/api/v1/households/me", headers=joiner.headers)
    assert r.json()["is_implicit"] is True and r.json()["members"][0]["preferred_view"] == "single"

async def test_preferred_view_single_only_when_alone(client, make_user_complete):
    u = await make_user_complete()
    r = await client.patch(f"/api/v1/households/{u.household.id}/members/me", json={"preferred_view": "family"}, headers=u.headers)
    assert r.status_code == 422

async def test_patch_household_slots_and_schedule(client, make_user_complete):
    u = await make_user_complete()
    body = {"name": "Sharma kitchen", "slots": [{"key":"lunch","label":"Lunch","order":1},{"key":"dinner","label":"Dinner","order":2}],
            "weekly_refresh_day": 5, "weekly_refresh_time": "20:00:00", "timezone": "Europe/London"}
    r = await client.patch(f"/api/v1/households/{u.household.id}", json=body, headers=u.headers)
    assert r.status_code == 200 and r.json()["is_implicit"] is False and len(r.json()["slots"]) == 2
```

- [x] **Step 2: Run to verify failure** → FAIL.

- [x] **Step 3: Implement** service and router per LLD §6.5 and §4.3. Invite code alphabet `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`, 8 chars via `secrets.choice`. Timezone validated with `zoneinfo.ZoneInfo(tz)` (raise `validation("unknown timezone", field="timezone")`). Slots: 1–6, unique keys, re-sorted by `order`.

- [x] **Step 4: Run** `uv run pytest -v` → PASS. **Step 5: Commit** `feat(api): households, invites, membership`.

---

# Phase 3 — Pantry

### Task 8: Normalisation, keyword map and categoriser

**Files:**
- Modify: `services/normalize.py` (complete per LLD §7.1)
- Create: `agents/categorize/__init__.py`, `agents/categorize/keyword_map.py`, `agents/categorize/categorize.py`, `agents/categorize/schemas.py`
- Test: `tests/unit/test_normalize.py`, `tests/unit/test_keyword_map.py`, `tests/agents/test_categorize.py`

**Interfaces:**
- Produces: `normalize_name(str) -> str`, `tokens(str) -> set[str]`, `ingredient_matches_pantry(ingredient_norm, pantry_norms: set[str]) -> str | None`; `KEYWORDS: dict[str, str]` (≥ 250 entries), `SUGGESTIONS: list[tuple[str, str]]` (≥ 60), `CATEGORY_ORDER: list[str]`, `CATEGORY_LABELS: dict[str, str]`; `class CategoryAssignments(BaseModel): assignments: list[CategoryAssignment(name: str, category: PantryCategory)]`; `async categorize(llm, names: list[str]) -> dict[str, str]` (keys are the input names as given).

- [x] **Step 1: Write failing tests**

```python
# tests/unit/test_normalize.py
from larder.services.normalize import normalize_name, ingredient_matches_pantry
import pytest

@pytest.mark.parametrize("raw,expected", [("Fresh Spinach leaves","spinach leaf"),("Tomatoes","tomato"),("Paneer cubes","paneer cube"),
                                          ("2 cups of basmati rice","2 basmati rice"),("Toor Dal","toor dal"),("chillies","chillie")])
def test_normalize(raw, expected): assert normalize_name(raw) == expected

def test_match_exact_then_token_subset():
    pantry = {"paneer", "spinach", "basmati rice"}
    assert ingredient_matches_pantry("paneer cube", pantry) == "paneer"
    assert ingredient_matches_pantry("basmati rice", pantry) == "basmati rice"
    assert ingredient_matches_pantry("cream", pantry) is None

# tests/unit/test_keyword_map.py
from larder.agents.categorize.keyword_map import KEYWORDS, SUGGESTIONS, CATEGORY_ORDER
def test_map_size_and_values():
    assert len(KEYWORDS) >= 250 and set(KEYWORDS.values()) <= set(CATEGORY_ORDER)
    assert KEYWORDS["paneer"] == "dairy" and KEYWORDS["toor dal"] == "pulses" and KEYWORDS["cumin"] == "spices"
    assert len(SUGGESTIONS) >= 60

# tests/agents/test_categorize.py
from larder.agents.categorize.categorize import categorize
from larder.agents.categorize.schemas import CategoryAssignments, CategoryAssignment
from larder.llm.fake import FakeLLM
from larder.llm.base import LLMError

async def test_map_hits_skip_llm_and_unknowns_go_to_llm():
    llm = FakeLLM(); llm.script_structured(CategoryAssignments, [CategoryAssignments(assignments=[CategoryAssignment(name="gundruk", category="vegetables")])])
    out = await categorize(llm, ["Paneer", "red onion", "gundruk"])
    assert out == {"Paneer": "dairy", "red onion": "vegetables", "gundruk": "vegetables"}
    assert len(llm.calls) == 1 and "gundruk" in llm.calls[0]["user"] and "Paneer" not in llm.calls[0]["user"]

async def test_llm_failure_falls_back_to_other():
    llm = FakeLLM(); llm.fail_next(LLMError("x"))
    assert (await categorize(llm, ["mystery"]))["mystery"] == "other"
```

- [x] **Step 2: Run to verify failure** → FAIL. **Step 3: Implement** per LLD §7.1 and §8.4. The keyword map must include Indian staples across all categories (dals, flours, spices, vegetables, fruits, dairy, proteins) plus common global items.

- [x] **Step 4: Run** → PASS. **Step 5: Commit** `feat(api): name normalisation and pantry categoriser`.

---

### Task 9: Pantry service and router

**Files:**
- Create: `services/pantry.py`, `schemas/pantry.py`, `routers/pantry.py`; Modify: `main.py`
- Test: `tests/integration/test_pantry.py`

**Interfaces:**
- Produces: `list_grouped(session, household_id) -> PantryGrouped`; `add_items(session, llm, household, added_by, items: list[PantryItemIn]) -> tuple[list[PantryItem], list[PantryItem]]`; `update_item`, `delete_item`; `suggestions(session, household_id) -> list[dict]`; endpoints LLD §6.6.

- [x] **Step 1: Write failing tests**

```python
async def test_bulk_add_groups_and_dedupes(client, make_user_complete):
    u = await make_user_complete()
    r = await client.post("/api/v1/pantry/items", json={"items": [{"name": "Paneer"}, {"name": "paneer "}, {"name": "Toor dal"}, {"name": "Spinach", "category": "vegetables"}]}, headers=u.headers)
    assert r.status_code == 201 and len(r.json()["created"]) == 3
    r = await client.get("/api/v1/pantry", headers=u.headers)
    cats = {c["category"]: [i["name"] for i in c["items"]] for c in r.json()["categories"]}
    assert cats["dairy"] == ["Paneer"] and cats["pulses"] == ["Toor dal"] and r.json()["total"] == 3

async def test_re_adding_unavailable_item_flips_available(client, make_user_complete):
    u = await make_user_complete()
    r = await client.post("/api/v1/pantry/items", json={"items": [{"name": "Onion"}]}, headers=u.headers)
    item_id = r.json()["created"][0]["id"]
    await client.patch(f"/api/v1/pantry/items/{item_id}", json={"is_available": False}, headers=u.headers)
    r = await client.post("/api/v1/pantry/items", json={"items": [{"name": "onion"}]}, headers=u.headers)
    assert r.json()["existing"][0]["is_available"] is True and r.json()["created"] == []

async def test_other_household_cannot_touch_item(client, make_user_complete):
    a = await make_user_complete("A"); b = await make_user_complete("B")
    r = await client.post("/api/v1/pantry/items", json={"items": [{"name": "Onion"}]}, headers=a.headers)
    item_id = r.json()["created"][0]["id"]
    assert (await client.delete(f"/api/v1/pantry/items/{item_id}", headers=b.headers)).status_code == 404

async def test_suggestions_exclude_present(client, make_user_complete):
    u = await make_user_complete()
    await client.post("/api/v1/pantry/items", json={"items": [{"name": "onion"}]}, headers=u.headers)
    r = await client.get("/api/v1/pantry/suggestions", headers=u.headers)
    assert "onion" not in [i["name"] for i in r.json()["items"]]
```

- [x] **Step 2: Run to verify failure** → FAIL. **Step 3: Implement** per LLD §6.6 (categoriser used only for items with no category; `llm` from `request.app.state.llm`). **Step 4: Run** → PASS. **Step 5: Commit** `feat(api): pantry endpoints`.

---

# Phase 4 — Meal library

### Task 10: Meal enrichment agent and fake handlers module

**Files:**
- Create: `agents/enrichment/__init__.py`, `agents/enrichment/schemas.py`, `agents/enrichment/prompts.py`, `agents/enrichment/enrich.py`, `agents/planner/vocab.py` (allergens, diet tags, DIET_COMPAT per LLD §7.3), `llm/fake_handlers.py`
- Modify: `llm/fake.py` (call `register_default_handlers(self)` in `__init__`)
- Test: `tests/agents/test_enrichment.py`, `tests/unit/test_diet_matrix.py`

**Interfaces:**
- Produces: `IngredientDraft`, `MealEnrichment` (LLD §8.3), `enrich_meal(llm, *, name, description, ingredients, instructions, slot_keys) -> MealEnrichment`; `vocab.ALLERGENS`, `vocab.DIET_TAGS`, `vocab.diet_ok(diet_type: str, diet_tags: list[str]) -> bool`; `fake_handlers.register_default_handlers(fake)` registering `MealEnrichment` and `CategoryAssignments` handlers (planner and onboarding handlers are added in Tasks 12 and 17).

- [x] **Step 1: Write failing tests**

```python
# tests/unit/test_diet_matrix.py
from larder.agents.planner.vocab import diet_ok
def test_matrix():
    assert diet_ok("vegan", ["vegan"]) and not diet_ok("vegan", ["vegetarian"])
    assert diet_ok("vegetarian", ["vegan"]) and not diet_ok("vegetarian", ["eggetarian"])
    assert diet_ok("jain", ["jain"]) and not diet_ok("jain", ["vegan"])
    assert diet_ok("omnivore", ["contains_meat"]) and diet_ok("other", [])

# tests/agents/test_enrichment.py
from larder.agents.enrichment.enrich import enrich_meal
from larder.llm.fake import FakeLLM

async def test_default_fake_enrichment_keeps_user_ingredients():
    llm = FakeLLM()
    out = await enrich_meal(llm, name="Palak paneer", description=None, ingredients=["spinach", "paneer", "cream"], instructions=None, slot_keys=["lunch","dinner"])
    names = [i.name for i in out.ingredients]
    assert {"spinach", "paneer", "cream"} <= set(names) and out.prep_minutes >= 5 and set(out.meal_types) <= {"lunch","dinner","any"}

async def test_unknown_tags_are_dropped():
    from larder.agents.enrichment.schemas import MealEnrichment, IngredientDraft
    llm = FakeLLM()
    llm.script_structured(MealEnrichment, [MealEnrichment(description="d", cuisine="x", meal_types=["dinner"], diet_tags=["vegetarian","keto!!"],
                                                          allergens=["dairy","unicorn"], prep_minutes=20, ingredients=[IngredientDraft(name="a", category="other")])])
    out = await enrich_meal(llm, name="X", description=None, ingredients=None, instructions=None, slot_keys=["dinner"])
    assert out.diet_tags == ["vegetarian"] and out.allergens == ["dairy"]
```

- [x] **Step 2: Run to verify failure** → FAIL. **Step 3: Implement.** Fake `MealEnrichment` handler: reads `ingredients` and `slot_keys` from context; returns those ingredients (category via `KEYWORDS`, else `other`; marks `salt/oil/water/sugar` staple) plus `["onion","salt"]` if fewer than 2; `diet_tags=["vegetarian"]` unless any ingredient token is in `{chicken, mutton, fish, egg, prawn}`; `allergens` derived (`paneer/milk/cream/ghee/curd → dairy`, `egg → egg`); `prep_minutes=30`; `meal_types=[first non-breakfast slot key]`.

- [x] **Step 4: Run** → PASS. **Step 5: Commit** `feat(api): meal enrichment agent and diet vocabulary`.

---

### Task 11: Meals service, router and feedback

**Files:**
- Create: `services/meals.py`, `schemas/meals.py`, `routers/meals.py`; Modify: `main.py`
- Test: `tests/integration/test_meals.py`

**Interfaces:**
- Produces: `create_meal(session, llm, household, created_by, body) -> Meal`; `list_meals(session, household_id, query, meal_type, source) -> list[Meal]`; `get_meal`, `update_meal`, `delete_meal` (409 if referenced by an active plan), `re_enrich`; `add_feedback(session, household_id, member_id, meal_id, kind, plan_entry_id, comment) -> FeedbackSummary`; `feedback_summary(session, household_id, meal_ids) -> dict[UUID, FeedbackSummary]`; `MealOut.from_model(meal, summary)`; endpoints LLD §6.7.

- [x] **Step 1: Write failing tests**

```python
async def test_create_meal_enriches(client, make_user_complete):
    u = await make_user_complete()
    r = await client.post("/api/v1/meals", json={"name": "Palak paneer", "ingredients": ["spinach", "paneer"]}, headers=u.headers)
    assert r.status_code == 201
    m = r.json(); assert m["enrichment_status"] == "complete" and m["source"] == "user" and len(m["ingredients"]) >= 2

async def test_duplicate_name_conflicts(client, make_user_complete):
    u = await make_user_complete()
    await client.post("/api/v1/meals", json={"name": "Dal"}, headers=u.headers)
    assert (await client.post("/api/v1/meals", json={"name": "dal "}, headers=u.headers)).status_code == 409

async def test_enrichment_failure_saves_raw(client, make_user_complete, fake_llm):
    from larder.llm.base import LLMError
    u = await make_user_complete(); fake_llm.fail_next(LLMError("down"))
    r = await client.post("/api/v1/meals", json={"name": "Khichdi", "ingredients": ["rice", "moong dal"]}, headers=u.headers)
    assert r.status_code == 201 and r.json()["enrichment_status"] == "failed" and [i["name"] for i in r.json()["ingredients"]] == ["rice", "moong dal"]

async def test_feedback_up_replaces_down_and_cooked_appends(client, make_user_complete):
    u = await make_user_complete()
    mid = (await client.post("/api/v1/meals", json={"name": "Dal"}, headers=u.headers)).json()["id"]
    await client.post(f"/api/v1/meals/{mid}/feedback", json={"kind": "down"}, headers=u.headers)
    r = await client.post(f"/api/v1/meals/{mid}/feedback", json={"kind": "up"}, headers=u.headers)
    assert r.json()["feedback"] == {"up": 1, "down": 0, "cooked": 0, "last_cooked_at": None}
    r = await client.post(f"/api/v1/meals/{mid}/feedback", json={"kind": "cooked"}, headers=u.headers)
    assert r.json()["feedback"]["cooked"] == 1 and r.json()["feedback"]["last_cooked_at"] is not None

async def test_list_filters_and_search(client, make_user_complete):
    u = await make_user_complete()
    await client.post("/api/v1/meals", json={"name": "Poha"}, headers=u.headers); await client.post("/api/v1/meals", json={"name": "Dal"}, headers=u.headers)
    r = await client.get("/api/v1/meals?query=po", headers=u.headers)
    assert [m["name"] for m in r.json()["meals"]] == ["Poha"]
```

- [x] **Step 2: Run to verify failure** → FAIL. **Step 3: Implement** per LLD §6.7 (search is `ILIKE %query%` on name; `meal_type` filters `meal_types @> ARRAY[x]` or contains `any`). **Step 4: Run** → PASS. **Step 5: Commit** `feat(api): meal library and feedback`.

---

# Phase 5 — Onboarding agent

### Task 12: Onboarding fields, widgets, state and graph

**Files:**
- Create: `agents/onboarding/__init__.py`, `fields.py`, `widgets.py`, `state.py`, `prompts.py`, `graph.py`, `schemas.py` (`ProfileDraft`, `ParsedFieldAnswer`)
- Modify: `llm/fake_handlers.py` (handlers for `ParsedFieldAnswer`; `complete_text` default already fine)
- Test: `tests/unit/test_fields.py`, `tests/agents/test_onboarding_flow.py`

**Interfaces:**
- Produces: `FIELDS: list[FieldSpec]` where `FieldSpec(name, description, widget: Widget, validate: Callable[[Any], Any], default_question: str, condition: Callable[[dict], bool] | None)`; `next_field(draft: dict) -> FieldSpec | None`; `coerce_widget_value(field, value) -> Any`; `ProfileDraft(BaseModel)` with all 15 fields optional; `build_onboarding_graph(checkpointer) -> CompiledGraph`; `async run_turn(graph, llm, user_id, last_answer: dict | None) -> TurnResult(message, widget, field, draft, progress, is_complete)`.

- [x] **Step 1: Write failing tests**

```python
# tests/unit/test_fields.py
from larder.agents.onboarding.fields import FIELDS, next_field, coerce_widget_value
def test_order_and_conditional_medical_notes():
    assert [f.name for f in FIELDS][:3] == ["display_name", "date_of_birth", "sex"]
    draft = {f.name: "x" for f in FIELDS if f.name not in {"medical_notes"}}
    draft["medical_conditions"] = ["none"]
    assert next_field(draft) is None
    draft["medical_conditions"] = ["type 2 diabetes"]
    assert next_field(draft).name == "medical_notes"
def test_validation_rejects_bad_height():
    import pytest
    f = next(x for x in FIELDS if x.name == "height_cm")
    with pytest.raises(ValueError): f.validate(coerce_widget_value(f, 900))

# tests/agents/test_onboarding_flow.py
from langgraph.checkpoint.memory import MemorySaver
from larder.agents.onboarding.graph import build_onboarding_graph, run_turn
from larder.agents.onboarding.schemas import ParsedFieldAnswer
from larder.llm.fake import FakeLLM

ANSWERS = {"display_name": "Priya", "date_of_birth": "1995-04-02", "sex": "female", "height_cm": 165, "weight_kg": 58, "activity_level": "moderate",
           "diet_type": "vegetarian", "cuisines": ["north_indian"], "allergens": ["peanut"], "dislikes": ["bitter gourd"], "likes": ["paneer"],
           "medical_conditions": ["type 2 diabetes"], "medical_notes": "avoid sugar", "goals": ["eat_healthier"], "cooking_skill": "intermediate", "max_prep_minutes": "30"}

async def test_full_conversation_with_one_invalid_and_one_text_answer():
    llm = FakeLLM(); graph = build_onboarding_graph(MemorySaver())
    t = await run_turn(graph, llm, "u1", None)
    assert t.field == "display_name" and t.widget.type == "text" and not t.is_complete
    steps = 0
    while not t.is_complete:
        if t.field == "height_cm" and steps == 3:
            t = await run_turn(graph, llm, "u1", {"kind": "widget", "value": 900}); assert t.field == "height_cm"; steps += 1; continue
        if t.field == "weight_kg":
            llm.script_structured(ParsedFieldAnswer, [ParsedFieldAnswer(value=58, confidence=0.9)])
            t = await run_turn(graph, llm, "u1", {"kind": "text", "text": "about 58 kilos"}); steps += 1; continue
        t = await run_turn(graph, llm, "u1", {"kind": "widget", "value": ANSWERS[t.field]}); steps += 1
    assert t.widget.type == "review" and t.draft.weight_kg == 58 and t.progress.answered == 16
```

- [x] **Step 2: Run to verify failure** → FAIL. **Step 3: Implement** per LLD §8.1. `run_turn` invokes `graph.ainvoke({"last_answer": last_answer, "user_id": user_id}, config={"configurable": {"thread_id": f"onb_{user_id}", "llm": llm}})`; nodes read `llm` from `config["configurable"]["llm"]`. State reducers: `draft` merges dicts; `history` appends and trims to 20. Fake `ParsedFieldAnswer` default handler returns `value=None, confidence=0` (so unscripted text answers re-ask). `progress.total` counts fields whose condition holds for the current draft.

- [x] **Step 4: Run** → PASS. **Step 5: Commit** `feat(api): onboarding agent graph`.

---

### Task 13: Onboarding router with Postgres checkpointer

**Files:**
- Create: `schemas/onboarding.py`, `routers/onboarding.py`; Modify: `main.py` (lifespan sets up `AsyncPostgresSaver` from `settings.checkpoint_database_url`, calls `await saver.setup()`, stores `app.state.onboarding_graph`), `services/profiles.py` (`apply_draft(profile, draft, overrides)`), `services/households.py` (used for implicit household)
- Test: `tests/integration/test_onboarding.py`

**Interfaces:**
- Produces: endpoints LLD §6.4 (`/onboarding/complete` returns `first_plan_job_id: None` until Task 18 wires plan generation; Task 18 modifies this router).

- [x] **Step 1: Write failing tests**

```python
import uuid
from tests.conftest import auth_headers

async def _answer_all(client, headers):
    from tests.agents.test_onboarding_flow import ANSWERS
    t = (await client.post("/api/v1/onboarding/start", headers=headers)).json()
    while not t["is_complete"]:
        t = (await client.post("/api/v1/onboarding/turn", json={"thread_id": t["thread_id"], "answer": {"kind": "widget", "value": ANSWERS[t["field"]]}}, headers=headers)).json()
    return t

async def test_start_is_idempotent_and_state_persists(client):
    h = auth_headers(uuid.uuid4())
    a = (await client.post("/api/v1/onboarding/start", headers=h)).json()
    await client.post("/api/v1/onboarding/turn", json={"thread_id": a["thread_id"], "answer": {"kind": "widget", "value": "Priya"}}, headers=h)
    b = (await client.post("/api/v1/onboarding/start", headers=h)).json()
    assert b["field"] == "date_of_birth" and b["draft"]["display_name"] == "Priya"

async def test_complete_creates_profile_and_implicit_household(client):
    h = auth_headers(uuid.uuid4())
    t = await _answer_all(client, h)
    r = await client.post("/api/v1/onboarding/complete", json={"thread_id": t["thread_id"], "overrides": {"likes": ["paneer", "rajma"]}}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["onboarding_status"] == "complete" and body["household"]["is_implicit"] is True and body["profile"]["likes"] == ["paneer", "rajma"]
    assert body["household"]["name"] == "Priya's kitchen"
    assert (await client.post("/api/v1/onboarding/start", headers=h)).status_code == 409

async def test_household_endpoints_blocked_before_onboarding(client):
    h = auth_headers(uuid.uuid4())
    r = await client.get("/api/v1/pantry", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "onboarding_incomplete"
```

- [x] **Step 2: Run to verify failure** → FAIL. **Step 3: Implement.** Checkpointer: `AsyncPostgresSaver.from_conn_string(url)` is a context manager; keep it open for the app lifetime inside `lifespan` (`saver = await stack.enter_async_context(AsyncPostgresSaver.from_conn_string(url))`, `await saver.setup()`). In tests the same Postgres is used; add `checkpoint*` tables to nothing (they are not truncated; thread ids are per random user id).

- [x] **Step 4: Run** → PASS. **Step 5: Commit** `feat(api): onboarding endpoints with postgres checkpointer`.

---

# Phase 6 — Planner

### Task 14: Planner state, medical rules, context loader and inputs hash

**Files:**
- Create: `agents/planner/__init__.py`, `agents/planner/state.py` (all models LLD §8.2), `agents/planner/medical_rules.py`, `agents/planner/context.py`, `services/hashing.py`
- Test: `tests/unit/test_medical_rules.py`, `tests/unit/test_hashing.py`, `tests/integration/test_context_loader.py`

**Interfaces:**
- Produces: `PlannerInput, MemberCtx, PantryCtx, IngredientCtx, MealCtx, FixedEntryCtx, PlanningContext, MealCandidate, NewMealDraft, IngredientDraft (re-export from enrichment), VariationDraft, EntryDraft, PlanDraft, PlannerState`; `medical_rules.rules_for(conditions: list[dict]) -> MedicalRules(hard_allergens: set[str], avoid_tokens: set[str])`; `async load_context(session, inp: PlannerInput) -> PlanningContext`; `compute_inputs_hash(ctx) -> str`.

- [x] **Step 1: Write failing tests**

```python
# tests/unit/test_medical_rules.py
from larder.agents.planner.medical_rules import rules_for
def test_celiac_and_diabetes():
    r = rules_for([{"name": "Celiac disease"}, {"name": "Type 2 Diabetes", "notes": ""}])
    assert "gluten" in r.hard_allergens and "sugar" in r.avoid_tokens and "jaggery" in r.avoid_tokens

# tests/unit/test_hashing.py
from larder.services.hashing import compute_inputs_hash
def test_hash_changes_with_pantry_but_not_feedback(planning_context_factory):
    a = planning_context_factory(pantry=["onion"]); b = planning_context_factory(pantry=["onion", "tomato"])
    c = planning_context_factory(pantry=["onion"]); c.library[0].feedback_up = 5
    assert compute_inputs_hash(a) != compute_inputs_hash(b) and compute_inputs_hash(a) == compute_inputs_hash(c)

# tests/integration/test_context_loader.py
from datetime import date, timedelta
async def test_load_context_week_and_today(client, make_user_complete, db_session):
    from larder.agents.planner.context import load_context
    from larder.agents.planner.state import PlannerInput
    import uuid
    u = await make_user_complete()
    await client.post("/api/v1/pantry/items", json={"items": [{"name": "spinach"}, {"name": "paneer"}]}, headers=u.headers)
    await client.post("/api/v1/meals", json={"name": "Palak paneer", "ingredients": ["spinach", "paneer", "cream"]}, headers=u.headers)
    start = date.today()
    inp = PlannerInput(job_id=uuid.uuid4(), plan_id=uuid.uuid4(), household_id=u.household.id, scope="single", member_id=u.profile.id,
                       mode="week", start_date=start, end_date=start + timedelta(days=6))
    ctx = await load_context(db_session, inp)
    assert len(ctx.requested) == 28 and len(ctx.members) == 1 and len(ctx.library) == 1 and {p.normalized_name for p in ctx.pantry} == {"spinach", "paneer"}
```
Add a `planning_context_factory` fixture in `tests/conftest.py` that builds an in-memory `PlanningContext` with one member, the given pantry names and one library meal ("Dal", ingredients dal/onion).

- [x] **Step 2: Run to verify failure** → FAIL. **Step 3: Implement** per LLD §7.3, §7.4, §8.2. `load_context` loads members via `HouseholdMember` (scope single → only `member_id`), pantry, library meals with ingredients and feedback aggregates (`feedback_summary` from Task 11), `recent_meal_ids` from `plan_entries` joined to `meal_plans` of the household with `date` in `[start-14, start)`, `fixed_entries` for today/slot modes, `requested` pairs as LLD §8.2. `age` from `date_of_birth`.

- [x] **Step 4: Run** → PASS. **Step 5: Commit** `feat(api): planner context, medical rules and inputs hash`.

---

### Task 15: Shortlist and coverage

**Files:**
- Create: `agents/planner/shortlist.py`, `services/coverage.py`
- Test: `tests/unit/test_coverage.py`, `tests/unit/test_shortlist.py`

**Interfaces:**
- Produces: `coverage.compute(ingredients: list[IngredientCtx], pantry_norms: set[str]) -> CoverageResult(coverage: float, covered: list[str], missing: list[IngredientCtx])`; `shortlist.build(ctx: PlanningContext, start_date: date) -> list[MealCandidate]` (LLD §8.2 shortlist rules); `shortlist.hard_conflict(meal: MealCtx, members: list[MemberCtx]) -> str | None` (reason string or None).

- [x] **Step 1: Write failing tests**

```python
# tests/unit/test_coverage.py
from larder.services.coverage import compute
from larder.agents.planner.state import IngredientCtx
def ing(n, staple=False, opt=False): return IngredientCtx(name=n, normalized_name=n, category="other", is_staple=staple, is_optional=opt)
def test_staples_ignored_and_ratio():
    r = compute([ing("spinach"), ing("paneer"), ing("cream", opt=True), ing("salt", staple=True)], {"spinach", "paneer"})
    assert r.coverage == 2/3 and r.covered == ["spinach", "paneer"] and [m.name for m in r.missing] == ["cream"]
def test_empty_countable_is_full(): assert compute([ing("salt", staple=True)], set()).coverage == 1.0

# tests/unit/test_shortlist.py
from datetime import date, timedelta
from larder.agents.planner.shortlist import build, hard_conflict
def test_allergen_conflict_excluded(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal", "onion"]); ctx.members[0].allergens = ["dairy"]
    ctx.library[0].allergens = ["dairy"]
    assert hard_conflict(ctx.library[0], ctx.members) is not None and build(ctx, date.today()) == []
def test_scoring_prefers_coverage_and_penalises_recent(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal", "onion"])
    m = ctx.library[0].model_copy(update={"id": __import__("uuid").uuid4(), "name": "Recent dal", "last_used_date": date.today() - timedelta(days=2)})
    ctx.library.append(m)
    ranked = build(ctx, date.today())
    assert ranked[0].meal.name == "Dal" and ranked[0].coverage == 1.0 and ranked[1].score < ranked[0].score
```

- [x] **Step 2: Run to verify failure** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit** `feat(api): planner shortlist and coverage scoring`.

---

### Task 16: Validator and fallback fill

**Files:**
- Create: `agents/planner/validate.py`, `agents/planner/fallback.py`
- Test: `tests/unit/test_validate.py`, `tests/unit/test_fallback.py`

**Interfaces:**
- Produces: `validate(draft: PlanDraft, ctx: PlanningContext, shortlist: list[MealCandidate]) -> ValidationResult(violations: list[str], warnings: list[str], bad_entry_indexes: set[int])`; `fallback_fill(draft: PlanDraft | None, result: ValidationResult, ctx, shortlist) -> PlanDraft`; `SIMPLE_BOWL(slot_key) -> NewMealDraft` (LLD §5.3 definition).

- [x] **Step 1: Write failing tests**

```python
# tests/unit/test_validate.py
from datetime import date
from larder.agents.planner.validate import validate
from larder.agents.planner.state import PlanDraft, EntryDraft, NewMealDraft, IngredientDraft
def new_meal(name, allergens=(), tags=("vegetarian",), ings=("dal","rice")):
    return NewMealDraft(name=name, description="d", cuisine="north_indian", meal_types=["dinner"], diet_tags=list(tags), allergens=list(allergens), prep_minutes=30,
                        ingredients=[IngredientDraft(name=i, category="other") for i in ings])
def test_allergen_and_missing_slot_are_violations(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal"]); ctx.members[0].allergens = ["peanut"]
    ctx.requested = [(date(2026,9,21), "lunch"), (date(2026,9,21), "dinner")]
    draft = PlanDraft(entries=[EntryDraft(date=date(2026,9,21), slot_key="lunch", new_meal=new_meal("Satay", allergens=["peanut"]), reason="r")])
    res = validate(draft, ctx, [])
    assert any("peanut" in v for v in res.violations) and any("dinner" in v for v in res.violations) and 0 in res.bad_entry_indexes
def test_dislike_is_warning_only(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal"]); ctx.members[0].dislikes = ["rice"]; ctx.requested = [(date(2026,9,21), "dinner")]
    draft = PlanDraft(entries=[EntryDraft(date=date(2026,9,21), slot_key="dinner", new_meal=new_meal("Dal rice"), reason="r")])
    res = validate(draft, ctx, []); assert res.violations == [] and res.warnings
def test_repeat_limit(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal"]); ctx.requested = [(date(2026,9,d), "dinner") for d in (21,22,23)]
    draft = PlanDraft(entries=[EntryDraft(date=date(2026,9,d), slot_key="dinner", new_meal=new_meal("Dal rice"), reason="r") for d in (21,22,23)])
    assert any("more than twice" in v for v in validate(draft, ctx, []).violations)

# tests/unit/test_fallback.py
from larder.agents.planner.fallback import fallback_fill
from larder.agents.planner.shortlist import build
from larder.agents.planner.validate import validate
def test_fallback_fills_everything_validly(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal", "onion"]); ctx.requested = [(date(2026,9,d), s) for d in (21,22,23) for s in ("lunch","dinner")]
    sl = build(ctx, date(2026,9,21))
    draft = fallback_fill(None, validate(PlanDraft(entries=[]), ctx, sl), ctx, sl)
    assert len(draft.entries) == 6 and validate(draft, ctx, sl).violations == []
```

- [x] **Step 2: Run to verify failure** → FAIL. **Step 3: Implement** per LLD §8.2 (hard and soft rules list; `bad_entry_indexes` = indexes of entries involved in any hard violation plus duplicates). Fallback uses shortlist candidates round-robin (max 2 uses each), then `SIMPLE_BOWL`. **Step 4: Run** → PASS. **Step 5: Commit** `feat(api): planner validator and deterministic fallback`.

---

### Task 17: Planner prompts, graph and persistence

**Files:**
- Create: `agents/planner/prompts.py` (system prompts verbatim from LLD §8.2), `agents/planner/graph.py`, `agents/planner/persist.py`, `agents/planner/errors.py` (`PlannerError`)
- Modify: `llm/fake_handlers.py` (`PlanDraft` handler per LLD §5.3)
- Test: `tests/agents/test_planner_week.py`, `test_planner_today.py`, `test_planner_slot.py`, `test_planner_repair.py`, `test_planner_fallback.py`

**Interfaces:**
- Produces: `build_planner_graph() -> CompiledGraph`; `async run_planner(session_factory, llm, inp: PlannerInput) -> PlannerOutcome(plan_id, attempts, used_fallback, inputs_hash, entries_written: int)`; `persist(session, inp, ctx, draft, ...)`; `persist` also updates `plan_jobs` fields `attempts`, `used_fallback`, `model_name`, `inputs_hash`.

- [x] **Step 1: Write failing tests** (fixture `plan_setup` in conftest: creates user, pantry `spinach, paneer, rice, toor dal, onion, tomato`, library meals `Palak paneer`, `Dal tadka`, `Jeera rice`, `Poha`, and an active `meal_plans` row + queued `plan_jobs` row for the given mode; returns `PlannerInput`).

```python
# tests/agents/test_planner_week.py
from sqlalchemy import select
async def test_week_plan_fills_all_slots_with_reasons(plan_setup, db_session, fake_llm):
    from larder.agents.planner.graph import run_planner
    from larder.db.models import PlanEntry
    from larder.db.session import async_session_factory
    inp = await plan_setup(mode="week")
    out = await run_planner(async_session_factory, fake_llm, inp)
    entries = (await db_session.execute(select(PlanEntry).where(PlanEntry.plan_id == inp.plan_id))).scalars().all()
    assert len(entries) == 28 and all(e.reason for e in entries) and out.used_fallback is False
    assert any("spinach" in e.covered_ingredients for e in entries)

# tests/agents/test_planner_today.py
async def test_today_mode_only_touches_target_date(plan_setup, db_session, fake_llm):
    from larder.agents.planner.graph import run_planner
    from larder.db.session import async_session_factory
    from larder.db.models import PlanEntry
    week = await plan_setup(mode="week"); await run_planner(async_session_factory, fake_llm, week)
    before = {(e.date, e.slot_key): e.id for e in (await db_session.execute(select(PlanEntry).where(PlanEntry.plan_id == week.plan_id))).scalars()}
    today = await plan_setup(mode="today", plan_id=week.plan_id, target_date=week.start_date)
    await run_planner(async_session_factory, fake_llm, today)
    db_session.expire_all()
    after = {(e.date, e.slot_key): e.id for e in (await db_session.execute(select(PlanEntry).where(PlanEntry.plan_id == week.plan_id))).scalars()}
    changed = {k for k in before if before[k] != after.get(k)}
    assert changed and all(k[0] == week.start_date for k in changed)

# tests/agents/test_planner_slot.py
async def test_slot_mode_replaces_one_entry_and_passes_reason(plan_setup, db_session, fake_llm):
    ...  # same shape: run week, pick one entry, run slot with swap_reason="too heavy"; assert exactly one entry id changed and fake_llm.calls[-1]["user"] contains "too heavy"

# tests/agents/test_planner_repair.py
async def test_repair_loop_fixes_allergen_violation(plan_setup, fake_llm, db_session):
    # member allergic to dairy; script first PlanDraft to include a new meal with allergens=["dairy"]; default handler on repair
    ...
    assert out.attempts == 1 and out.used_fallback is False

# tests/agents/test_planner_fallback.py
async def test_three_bad_drafts_trigger_fallback(plan_setup, fake_llm):
    ...  # script three violating drafts; assert out.used_fallback is True and out.attempts == 2 and entries valid
```
Write the elided tests in full following the first two.

- [x] **Step 2: Run to verify failure** → FAIL. **Step 3: Implement** graph per LLD §8.2 (`StateGraph(PlannerState)`, conditional edges on `violations`/`attempts`), prompts verbatim, `persist` in one transaction. `run_planner` opens its own session for `load_context` and `persist`, sets `job.inputs_hash` right after context load and commits it (so the scheduler can compare even if drafting fails). Fake `PlanDraft` handler reads `requested`, `shortlist`, `slots` from context and fills round-robin.

- [x] **Step 4: Run** `uv run pytest tests/agents -v` → PASS. **Step 5: Commit** `feat(api): planner graph with repair loop and persistence`.

---

### Task 18: Plans service, job runner and plans router

**Files:**
- Create: `services/plans.py`, `jobs/__init__.py`, `jobs/runner.py`, `schemas/plans.py`, `routers/plans.py`
- Modify: `main.py`, `routers/onboarding.py` (complete → enqueue first week plan, return `first_plan_job_id`), `routers/households.py` (remove member → enqueue week plan for the new implicit household)
- Test: `tests/integration/test_plans.py`

**Interfaces:**
- Produces: `request_generation(session, user, scope, mode, date, origin, background) -> (job_id, plan_id)`; `request_swap(session, user, plan_id, entry_id, reason, background) -> job_id`; `get_current_plan(session, user, scope, date) -> CurrentPlanOut`; `get_job(session, user, job_id)`; `jobs.runner.enqueue(job_id, background)`, `run_job(job_id)`; endpoints LLD §6.8 (shopping list added in Task 19). Tests run background tasks inline: in `conftest`, an autouse fixture `inline_jobs` monkeypatches `larder.jobs.runner.enqueue` with `async def _inline(job_id, background): await run_job(job_id)`. For the patch to take effect, every caller must invoke it as a module attribute (`from larder.jobs import runner` … `await runner.enqueue(job_id, background)`), never `from larder.jobs.runner import enqueue`. `request_generation(..., start_date, end_date)` accepts an explicit `end_date` (default `start_date + 6`) so the scheduler's gap-fill plans (LLD §7.5) reuse it.

- [x] **Step 1: Write failing tests**

```python
from datetime import date
async def _seed(client, u):
    await client.post("/api/v1/pantry/items", json={"items": [{"name": n} for n in ["spinach","paneer","rice","toor dal","onion"]]}, headers=u.headers)
    await client.post("/api/v1/meals", json={"name": "Palak paneer", "ingredients": ["spinach","paneer"]}, headers=u.headers)

async def test_generate_week_then_current(client, make_user_complete):
    u = await make_user_complete(); await _seed(client, u)
    r = await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "week"}, headers=u.headers)
    assert r.status_code == 202
    job = (await client.get(f"/api/v1/plans/jobs/{r.json()['job_id']}", headers=u.headers)).json()
    assert job["status"] == "ready"
    cur = (await client.get("/api/v1/plans/current?scope=single", headers=u.headers)).json()
    assert cur["plan"]["id"] == r.json()["plan_id"] and len(cur["plan"]["days"]) == 7 and len(cur["plan"]["days"][0]["entries"]) == 4
    assert cur["plan"]["coverage"]["needed"] > 0 and cur["active_job"] is None

async def test_family_scope_rejected_when_alone(client, make_user_complete):
    u = await make_user_complete()
    assert (await client.post("/api/v1/plans/generate", json={"scope": "family", "mode": "week"}, headers=u.headers)).status_code == 422

async def test_swap_entry(client, make_user_complete):
    u = await make_user_complete(); await _seed(client, u)
    r = await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "week"}, headers=u.headers)
    cur = (await client.get("/api/v1/plans/current?scope=single", headers=u.headers)).json()
    entry = cur["plan"]["days"][0]["entries"][3]
    r = await client.post(f"/api/v1/plans/{cur['plan']['id']}/entries/{entry['id']}/swap", json={"reason": "too heavy"}, headers=u.headers)
    assert r.status_code == 202
    cur2 = (await client.get("/api/v1/plans/current?scope=single", headers=u.headers)).json()
    assert cur2["plan"]["days"][0]["entries"][3]["id"] != entry["id"]

async def test_new_week_supersedes_overlap(client, make_user_complete, db_session):
    u = await make_user_complete(); await _seed(client, u)
    a = (await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "week"}, headers=u.headers)).json()["plan_id"]
    b = (await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "week"}, headers=u.headers)).json()["plan_id"]
    from larder.db.models import MealPlan
    assert (await db_session.get(MealPlan, a)).status == "superseded" and a != b

async def test_onboarding_complete_enqueues_first_plan(client):
    import uuid
    from tests.conftest import auth_headers
    from tests.integration.test_onboarding import _answer_all
    h = auth_headers(uuid.uuid4()); t = await _answer_all(client, h)
    r = await client.post("/api/v1/onboarding/complete", json={"thread_id": t["thread_id"]}, headers=h)
    assert r.json()["first_plan_job_id"] is not None
    assert (await client.get("/api/v1/plans/current", headers=h)).json()["plan"] is not None
```

- [x] **Step 2: Run to verify failure** → FAIL. **Step 3: Implement** per LLD §6.8 and §7.6. `CurrentPlanOut` builds `days`, `coverage` (`on_hand` = sum of covered, `needed` = covered + non-optional missing), `my_feedback`, `cooked_count`, `unused_pantry` (Task 19 supplies the function; return `[]` until then), `active_job` = latest queued/running job.

- [x] **Step 4: Run** → PASS. **Step 5: Commit** `feat(api): plan generation, swap, job polling`.

---

# Phase 7 — Shopping list and unused pantry

### Task 19: Shopping list and unused pantry

**Files:**
- Create: `services/shopping.py`, `services/unused.py`; Modify: `routers/plans.py`, `services/plans.py` (fill `unused_pantry`)
- Test: `tests/unit/test_shopping.py`, `tests/unit/test_unused.py`, `tests/integration/test_shopping_endpoint.py`

**Interfaces:**
- Produces: `build_shopping_list(entries, meals_by_id, from_date) -> ShoppingListOut` (LLD §6.8 shape); `unused_pantry_items(pantry, entries, meals_by_id, today) -> list[dict]`; `GET /plans/{plan_id}/shopping-list`.

- [x] **Step 1: Write failing tests**

```python
# tests/unit/test_shopping.py
from datetime import date
from types import SimpleNamespace as NS
from larder.services.shopping import build_shopping_list
def test_groups_dedupes_and_drops_optional():
    e1 = NS(date=date(2026,9,18), meal_id="m1", missing_ingredients=[{"name":"Cream","category":"dairy","is_optional":False},{"name":"coriander","category":"vegetables","is_optional":True}])
    e2 = NS(date=date(2026,9,19), meal_id="m2", missing_ingredients=[{"name":"cream","category":"dairy","is_optional":False}])
    e0 = NS(date=date(2026,9,17), meal_id="m1", missing_ingredients=[{"name":"ghee","category":"dairy","is_optional":False}])
    out = build_shopping_list([e0, e1, e2], {"m1": NS(name="Palak paneer"), "m2": NS(name="Malai kofta")}, from_date=date(2026,9,18))
    assert out.total == 1 and out.groups[0].category == "dairy" and out.groups[0].items[0].name == "Cream" and out.groups[0].items[0].meals == ["Palak paneer", "Malai kofta"]

# tests/unit/test_unused.py
def test_unused_excludes_spices_and_used():
    from larder.services.unused import unused_pantry_items
    pantry = [NS(name="Cumin", normalized_name="cumin", category="spices", is_available=True), NS(name="Bottle gourd", normalized_name="bottle gourd", category="vegetables", is_available=True),
              NS(name="Paneer", normalized_name="paneer", category="dairy", is_available=True)]
    entries = [NS(date=date(2026,9,18), covered_ingredients=["paneer"])]
    assert [i["name"] for i in unused_pantry_items(pantry, entries, {}, date(2026,9,18))] == ["Bottle gourd"]
```
Integration test: generate a plan (as in Task 18) then `GET /plans/{id}/shopping-list` returns 200 with `groups` list and `total >= 0`.

- [x] **Step 2: Run to verify failure** → FAIL. **Step 3: Implement** per LLD §7.7, §7.8. **Step 4: Run** → PASS. **Step 5: Commit** `feat(api): shopping list and unused pantry hints`.

---

# Phase 8 — Scheduler

### Task 20: Scheduler tick

**Files:**
- Create: `services/scheduler.py`, `schemas/internal.py`, `routers/internal.py`; Modify: `main.py`
- Test: `tests/unit/test_scheduler_due.py`, `tests/integration/test_scheduler_tick.py`

**Interfaces:**
- Produces: `weekly_due(household, local_now) -> str | None` (period key when due), `daily_due(household, local_now) -> str | None`; `async run_tick(session, now_utc, enqueue) -> TickReport`; `POST /internal/scheduler/tick` guarded by `X-Scheduler-Secret`.

- [x] **Step 1: Write failing tests**

```python
# tests/unit/test_scheduler_due.py
from datetime import datetime, time
from types import SimpleNamespace as NS
from larder.services.scheduler import weekly_due, daily_due
H = NS(weekly_refresh_day=6, weekly_refresh_time=time(18,0), daily_refresh_time=time(6,0))
def test_weekly_due_on_sunday_evening():
    assert weekly_due(H, datetime(2026,9,20,18,5)) == "2026-W38"     # Sunday
    assert weekly_due(H, datetime(2026,9,20,17,55)) is None and weekly_due(H, datetime(2026,9,19,19,0)) is None
def test_daily_due_after_six():
    assert daily_due(H, datetime(2026,9,18,6,0)) == "2026-09-18" and daily_due(H, datetime(2026,9,18,5,59)) is None

# tests/integration/test_scheduler_tick.py
from datetime import datetime, timezone
HDR = {"X-Scheduler-Secret": "test-scheduler"}
async def test_bad_secret_forbidden(client):
    assert (await client.post("/api/v1/internal/scheduler/tick", headers={"X-Scheduler-Secret": "no"})).status_code == 403

async def test_daily_tick_creates_week_when_no_plan_then_skips_when_unchanged(client, make_user_complete, monkeypatch):
    u = await make_user_complete()   # tz Asia/Kolkata; 06:00 IST = 00:30 UTC
    import larder.services.scheduler as sched
    monkeypatch.setattr(sched, "utcnow", lambda: datetime(2026,9,18,1,0,tzinfo=timezone.utc))
    r = await client.post("/api/v1/internal/scheduler/tick", headers=HDR)
    assert len(r.json()["daily_enqueued"]) == 1
    r = await client.post("/api/v1/internal/scheduler/tick", headers=HDR)
    assert r.json()["daily_enqueued"] == [] and r.json()["skipped"] >= 1
    monkeypatch.setattr(sched, "utcnow", lambda: datetime(2026,9,19,1,0,tzinfo=timezone.utc))
    r = await client.post("/api/v1/internal/scheduler/tick", headers=HDR)
    assert r.json()["daily_enqueued"] == []          # inputs unchanged → skipped
    await client.post("/api/v1/pantry/items", json={"items": [{"name": "okra"}]}, headers=u.headers)
    monkeypatch.setattr(sched, "utcnow", lambda: datetime(2026,9,20,1,0,tzinfo=timezone.utc))
    r = await client.post("/api/v1/internal/scheduler/tick", headers=HDR)
    assert len(r.json()["daily_enqueued"]) == 1      # changed → today job

async def test_weekly_tick_idempotent(client, make_user_complete, monkeypatch):
    u = await make_user_complete()
    import larder.services.scheduler as sched
    monkeypatch.setattr(sched, "utcnow", lambda: datetime(2026,9,20,13,0,tzinfo=timezone.utc))   # Sunday 18:30 IST
    a = (await client.post("/api/v1/internal/scheduler/tick", headers=HDR)).json()
    b = (await client.post("/api/v1/internal/scheduler/tick", headers=HDR)).json()
    assert len(a["weekly_enqueued"]) == 1 and b["weekly_enqueued"] == []
    # daily step ran after weekly in tick `a`: no plan contained Sunday, so a one-day gap-fill plan (Sun..Sun) was created
    assert len(a["daily_enqueued"]) == 1
    from datetime import date
    from sqlalchemy import select
    from larder.db.models import MealPlan
    plans = (await db_session.execute(select(MealPlan).where(MealPlan.household_id == u.household.id, MealPlan.status == "active").order_by(MealPlan.start_date))).scalars().all()
    assert [(p.start_date, p.end_date) for p in plans] == [(date(2026,9,20), date(2026,9,20)), (date(2026,9,21), date(2026,9,27))]
```
(Add `db_session` to that test's fixture list.)

- [x] **Step 2: Run to verify failure** → FAIL. **Step 3: Implement** per LLD §7.5 with a module-level `utcnow()` for patching; weekly evaluated before daily for each household; gap-fill `end_date = min(today + 6, next_plan.start_date - 1)`; `refresh_runs` inserted with `ON CONFLICT DO NOTHING` before enqueueing; cleanup of old superseded plans. **Step 4: Run** `uv run pytest -q` → all PASS. **Step 5: Commit** `feat(api): scheduler tick endpoint`.

---

# Phase 9 — Shared packages

### Task 21: `@larder/design-tokens`

**Files:**
- Create: `packages/design-tokens/package.json`, `tsconfig.json`, `src/tokens.ts`, `src/css.ts`, `src/index.ts`, `src/tokens.test.ts`

**Interfaces:**
- Produces: `palette`, `type`, `space`, `radius`, `toCssVariables(theme)` exactly as LLD §9.1; package `main: dist/index.js`, `types: dist/index.d.ts`, scripts `build: tsc`, `test: vitest run`, `typecheck: tsc --noEmit`.

- [ ] **Step 1: Failing test**

```ts
import { describe, expect, it } from "vitest";
import { palette, toCssVariables } from "./index";
describe("tokens", () => {
  it("has one accent per theme and emits css vars", () => {
    expect(palette.light.accent).toBe("#B4532A");
    expect(toCssVariables("dark")).toContain("--accent:#E07A4B");
    expect(toCssVariables("light")).toMatch(/^:root\{/);
  });
});
```

- [ ] **Step 2: Run** `pnpm --filter @larder/design-tokens test` → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; `pnpm --filter @larder/design-tokens build`. **Step 5: Commit** `feat(tokens): design tokens package`.

---

### Task 22: `@larder/api-client`

**Files:**
- Create: `packages/api-client/package.json`, `tsconfig.json`, `scripts/gen.sh`, `src/schema.d.ts` (generated), `src/client.ts`, `src/provider.tsx`, `src/hooks/{me,onboarding,households,pantry,meals,plans}.ts`, `src/index.ts`, `src/client.test.ts`

**Interfaces:**
- Produces: `createApi(baseUrl, getToken)`, `ApiError`, `ApiProvider({api, children})`, `useApi()`, every hook listed in LLD §9.3 with the given query keys; deps `openapi-fetch`, `@tanstack/react-query` (peer `react`).

- [ ] **Step 1: Generate the schema** with the API running (`pnpm api` in another terminal): `scripts/gen.sh`:
```bash
#!/usr/bin/env sh
set -e
npx openapi-typescript "${API_URL:-http://localhost:8000}/openapi.json" -o src/schema.d.ts
```
Commit the generated file.

- [ ] **Step 2: Failing test**

```ts
import { describe, expect, it, vi } from "vitest";
import { createApi, ApiError } from "./client";
describe("createApi", () => {
  it("adds bearer token and converts error envelope", async () => {
    const fetchMock = vi.fn(async (req: Request) => {
      expect(req.headers.get("authorization")).toBe("Bearer t");
      return new Response(JSON.stringify({ error: { code: "conflict", message: "dup", details: null } }), { status: 409, headers: { "content-type": "application/json" } });
    });
    const api = createApi("http://x/api/v1", async () => "t", fetchMock as unknown as typeof fetch);
    await expect(api.request("GET", "/pantry")).rejects.toMatchObject({ code: "conflict", status: 409 } satisfies Partial<ApiError>);
  });
});
```

- [ ] **Step 3: Implement.** `createApi` returns an object with the typed `openapi-fetch` client as `raw` plus `request(method, path, init)` that throws `ApiError` on non-2xx. Hooks call `useApi()` and wrap `raw.GET/POST/...`. `useJob(jobId)` uses `refetchInterval: data => data?.status === "ready" || data?.status === "failed" ? false : 2000` and `onSuccess` invalidates `["plan"]` when ready (use `useEffect` on `data.status` since TanStack v5 removed `onSuccess`).

- [ ] **Step 4: Run** `pnpm --filter @larder/api-client test typecheck` → PASS. **Step 5: Commit** `feat(client): generated api client and query hooks`.

---

# Phase 10 — Web app

### Task 23: Next.js scaffold, theme, UI kit, auth pages, router page

**Files:**
- Create: `apps/web` via `pnpm create next-app@latest web --ts --app --tailwind --eslint --src-dir --no-import-alias` (run from `apps/`), then: `src/styles/globals.css`, `src/lib/theme.ts`, `src/lib/supabase/{client.ts,server.ts,middleware.ts}`, `src/middleware.ts` (or `src/proxy.ts` on Next 16+), `src/lib/api.tsx` (`AppProviders`: QueryClient + ApiProvider + ThemeProvider), `src/components/ui/{Button,Input,Select,Chip,Toggle,Sheet,Banner,Skeleton,EmptyState}.tsx`, `src/app/(auth)/sign-in/page.tsx`, `src/app/(auth)/sign-up/page.tsx`, `src/app/page.tsx`, `src/app/(app)/layout.tsx` (nav: Today, Week, Pantry, Meals, Shopping, Household, Profile), `tests/theme.test.tsx`, `vitest.config.ts`
- Deps: `@supabase/supabase-js @supabase/ssr @tanstack/react-query lucide-react @larder/api-client @larder/design-tokens`; dev `vitest @testing-library/react @testing-library/jest-dom jsdom @vitejs/plugin-react`

**Interfaces:**
- Produces: `ThemeProvider` + `useTheme()` returning `{theme, setTheme}` persisting to `localStorage["larder-theme"]` and setting `data-theme` on `<html>`; `globals.css` defines `:root` light vars, `[data-theme="dark"]` dark vars and `@media (prefers-color-scheme: dark) :root:not([data-theme="light"])`; Tailwind `@theme` maps `--color-bg`, `--color-surface`, `--color-ink`, `--color-ink-muted`, `--color-line`, `--color-accent`, etc.; fonts via `next/font/google` (Fraunces, Instrument Sans) exposed as `--font-display`, `--font-body`.

- [ ] **Step 1: Failing test**

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { ThemeProvider, useTheme } from "@/lib/theme";
function Probe() { const { theme, setTheme } = useTheme(); return <button onClick={() => setTheme("dark")}>{theme}</button>; }
it("persists theme and sets data-theme", () => {
  render(<ThemeProvider><Probe /></ThemeProvider>);
  fireEvent.click(screen.getByRole("button"));
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem("larder-theme")).toBe("dark");
});
```

- [ ] **Step 2: Run** `pnpm --filter web test` → FAIL. **Step 3: Implement** scaffold, providers, UI kit (each component ≤ 80 lines, uses only token classes, focus ring per LLD §9.2), auth pages (`supabase.auth.signUp`/`signInWithPassword`, inline error text, link between pages), middleware redirect, `src/app/page.tsx` calling `useMe()` and routing per LLD §9.4. Delete the Next.js boilerplate page content and default CSS.

- [ ] **Step 4: Run** `pnpm --filter web test typecheck lint` → PASS; `pnpm --filter web dev` and sign up against a Supabase project or `supabase start` local stack (document both in README). **Step 5: Commit** `feat(web): scaffold, theme, ui kit and auth`.

---

### Task 24: Web onboarding screen

**Files:**
- Create: `src/components/onboarding/{Transcript,WidgetRenderer,ReviewCard}.tsx`, `src/app/onboarding/page.tsx`, `tests/widget-renderer.test.tsx`

**Interfaces:**
- Produces: `WidgetRenderer({widget, onSubmit: (answer: {kind: "widget", value: unknown} | {kind: "text", text: string}) => void, disabled})`; `ReviewCard({draft, onConfirm(overrides), onEdit})`.

- [ ] **Step 1: Failing test**

```tsx
it("submits the right value shape per widget", () => {
  const onSubmit = vi.fn();
  const { rerender } = render(<WidgetRenderer widget={{ type: "number", unit: "cm", min: 50, max: 250, step: 1 }} onSubmit={onSubmit} />);
  fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "172" } }); fireEvent.click(screen.getByText("Continue"));
  expect(onSubmit).toHaveBeenLastCalledWith({ kind: "widget", value: 172 });
  rerender(<WidgetRenderer widget={{ type: "multi_select", options: [{ value: "a", label: "A" }, { value: "b", label: "B" }], allow_custom: false, min: 0, max: 5 }} onSubmit={onSubmit} />);
  fireEvent.click(screen.getByText("A")); fireEvent.click(screen.getByText("B")); fireEvent.click(screen.getByText("Continue"));
  expect(onSubmit).toHaveBeenLastCalledWith({ kind: "widget", value: ["a", "b"] });
  rerender(<WidgetRenderer widget={{ type: "text", placeholder: "", multiline: false, max_length: 40 }} onSubmit={onSubmit} />);
  fireEvent.click(screen.getByText("Type instead")); fireEvent.change(screen.getByRole("textbox"), { target: { value: "hi" } }); fireEvent.click(screen.getByText("Send"));
  expect(onSubmit).toHaveBeenLastCalledWith({ kind: "text", text: "hi" });
});
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** per LLD §9.6 (transcript, waiting state, review card → `useOnboardingComplete` → `router.replace("/pantry/setup")`). **Step 4: Run tests** → PASS; manual check of the whole conversation against the local API. **Step 5: Commit** `feat(web): onboarding conversation`.

---

### Task 25: Web pantry setup and pantry screens

**Files:**
- Create: `src/components/pantry/{CategorySection,QuickAdd,BulkAdd,SuggestionChips}.tsx`, `src/app/pantry/setup/page.tsx`, `src/app/(app)/pantry/page.tsx`, `tests/bulk-add.test.tsx`

**Interfaces:**
- Produces: `parseBulk(text: string): string[]` (splits on commas and newlines, trims, dedupes case-insensitively); `BulkAdd({onAdd(names)})`.

- [ ] **Step 1: Failing test**
```ts
import { parseBulk } from "@/components/pantry/BulkAdd";
it("parses commas and newlines", () => expect(parseBulk("Paneer, spinach\n toor dal,, Spinach")).toEqual(["Paneer", "spinach", "toor dal"]));
```
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** per LLD §9.4: setup page = textarea + suggestion chips (`usePantrySuggestions`) + "Add" + "Skip for now" → `/today`; pantry page = category sections, inline add per section, availability toggle (muted strike style when unavailable), rename on click, delete with undo-free confirm. **Step 4: Run** → PASS. **Step 5: Commit** `feat(web): pantry setup and pantry management`.

---

### Task 26: Web Today and Week screens with jobs, swap and feedback

**Files:**
- Create: `src/components/plan/{PlanEntryCard,SlotHeader,CoverageLine,SwapSheet,FeedbackBar,JobBanner,ViewToggle}.tsx`, `src/app/(app)/today/page.tsx`, `src/app/(app)/week/page.tsx`, `tests/plan-entry-card.test.tsx`

**Interfaces:**
- Produces: `PlanEntryCard({entry, onSwap(reason), onFeedback(kind)})` anatomy per LLD §9.4; `JobBanner({job, onRetry})` per LLD §9.7; `ViewToggle` (single/family, hidden when household has one member).

- [ ] **Step 1: Failing test**
```tsx
it("renders reason, coverage, variations and feedback state", () => {
  const entry = { id: "e", slot_label: "Dinner", reason: "Uses the spinach you have.", covered_ingredients: ["spinach"], missing_ingredients: [{ name: "cream", category: "dairy", is_optional: true }],
    variations: [{ member_id: "m", display_name: "Aarav", note: "no green chilli" }], my_feedback: "up", cooked_count: 0, meal: { name: "Palak paneer" } } as any;
  render(<PlanEntryCard entry={entry} onSwap={() => {}} onFeedback={() => {}} />);
  expect(screen.getByText("Palak paneer")).toBeInTheDocument();
  expect(screen.getByText(/Uses the spinach/)).toBeInTheDocument();
  expect(screen.getByText(/cream \(optional\)/)).toBeInTheDocument();
  expect(screen.getByText(/Aarav: no green chilli/)).toBeInTheDocument();
  expect(screen.getByLabelText("Thumbs up")).toHaveAttribute("aria-pressed", "true");
});
```
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** Today: header "Today, Thu 18 Sep" in display font, `CoverageLine` ("On hand for today: 8 of 11 ingredients"), "Unused this week: bottle gourd, okra" muted line, entries list, `JobBanner` when `active_job`, empty state "No plan yet" with "Plan my week" button (`useGeneratePlan`). Week: 7 columns ≥ 1024px, stacked below; "Regenerate week" with confirm sheet. Swap: sheet with reason chips ("Too heavy", "No time", "Had it recently", "Something else…" + text). **Step 4: Run** → PASS. **Step 5: Commit** `feat(web): today and week plan screens`.

---

### Task 27: Web meals library screens

**Files:**
- Create: `src/components/meals/{MealList,MealForm,IngredientList}.tsx`, `src/app/(app)/meals/page.tsx`, `src/app/(app)/meals/new/page.tsx`, `src/app/(app)/meals/[id]/page.tsx`, `tests/meal-form.test.tsx`

- [ ] **Step 1: Failing test:** `MealForm` submit calls `onSubmit({name, description, ingredients: ["spinach","paneer"], instructions})` when the ingredients textarea contains `"spinach\npaneer"`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** per LLD §9.4: list with search box and filters (meal type, source toggle "Mine / Suggested by Larder"); detail shows tags as chips, ingredient list with staple/optional markers, enrichment status note with "Try again" (`useEnrichMeal`), edit for user meals, delete with 409 message surfaced verbatim. **Step 4: Run** → PASS. **Step 5: Commit** `feat(web): meal library`.

---

### Task 28: Web shopping, household and profile screens

**Files:**
- Create: `src/app/(app)/shopping/page.tsx`, `src/app/(app)/household/page.tsx`, `src/app/(app)/profile/page.tsx`, `src/components/household/{MemberList,InviteCode,JoinForm,SlotsEditor,ScheduleForm}.tsx`, `tests/slots-editor.test.tsx`

- [ ] **Step 1: Failing test:** `SlotsEditor` prevents duplicate keys and emits slots re-numbered by order on save.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** per LLD §9.4. Household page sections: Members (owner sees Remove), Invite (owner: code in mono font with Copy; member: none), Join a household (code input; explains the implicit household will be replaced), Your view (ViewToggle), Meal slots, Refresh schedule (weekday select, two time inputs, timezone select from `Intl.supportedValuesOf("timeZone")`). Profile page: grouped editable fields with Save per group, "Clear health data" button, theme toggle, sign out, the non-medical-advice sentence. Shopping page: grouped list with local checkbox state and "Add to pantry" per item (`useAddPantryItems`). **Step 4: Run** → PASS. **Step 5: Commit** `feat(web): shopping, household and profile`.

---

### Task 29: Web end-to-end test

**Files:**
- Create: `apps/web/playwright.config.ts`, `apps/web/e2e/first-run.spec.ts`; Modify: `apps/web/package.json` (`e2e: playwright test`)

- [ ] **Step 1: Write the spec** per LLD §10.2 (`first-run.spec.ts`): unique email per run; sign up; loop: read the current widget type and answer (`page.getByTestId("widget-<type>")`); confirm review; bulk-add 5 pantry items; expect 4 `PlanEntryCard`s on Today (poll up to 60 s); open swap on the last card, choose "Too heavy", expect the card's meal name to change; click thumbs up; go to Shopping and expect at least one group.
- [ ] **Step 2: Run** with the API (`LLM_PROVIDER=fake`) and Supabase local running: `pnpm --filter web e2e` → PASS. Fix any selector or flow gaps found.
- [ ] **Step 3: Commit** `test(web): first-run end-to-end flow`.

---

# Phase 11 — Mobile app

### Task 30: Expo scaffold, providers, auth and theme

**Files:**
- Create: `apps/mobile` via `pnpm create expo-app@latest mobile --template tabs` (from `apps/`), then `src/lib/{supabase.ts,api.tsx,theme.tsx}`, `app/_layout.tsx`, `app/(auth)/{sign-in,sign-up}.tsx`, `app/index.tsx` (router per `useMe()`), `src/components/ui/{Button,Input,Chip,Toggle,Banner,Skeleton,EmptyState}.tsx`, `__tests__/theme.test.tsx`, `jest.config.js` (preset `jest-expo`)
- Deps: `@supabase/supabase-js expo-secure-store @react-native-async-storage/async-storage @tanstack/react-query expo-font @expo-google-fonts/fraunces @expo-google-fonts/instrument-sans lucide-react-native react-native-svg @larder/api-client @larder/design-tokens`

**Interfaces:**
- Produces: `ThemeProvider`/`useTheme()` returning `{mode, colors, setMode}` persisted in AsyncStorage key `larder-theme`; `supabase` client with SecureStore adapter and `AppState` auto-refresh; `AppProviders`.

- [ ] **Step 1: Failing test:** `useTheme().colors.accent` equals `#E07A4B` after `setMode("dark")`. **Step 2: Run** `pnpm --filter mobile test` → FAIL. **Step 3: Implement**; remove template screens. Metro must resolve workspace packages: add `watchFolders` for the monorepo root and `nodeModulesPaths` in `metro.config.js`. **Step 4: Run** → PASS; `pnpm --filter mobile start` and sign in on Expo Go. **Step 5: Commit** `feat(mobile): scaffold, theme, auth`.

---

### Task 31: Mobile onboarding and pantry setup

**Files:**
- Create: `app/onboarding.tsx`, `app/pantry-setup.tsx`, `src/components/onboarding/{Transcript,WidgetRenderer,ReviewCard}.tsx`, `src/components/pantry/{BulkAdd,SuggestionChips}.tsx`, `__tests__/widget-renderer.test.tsx`

- [ ] **Step 1: Failing test:** same assertions as Task 24 using `@testing-library/react-native` (`fireEvent.changeText`, `fireEvent.press`). **Step 2: Run** → FAIL. **Step 3: Implement** with `KeyboardAvoidingView`, `FlatList` transcript, native date picker (`@react-native-community/datetimepicker`). **Step 4: Run** → PASS. **Step 5: Commit** `feat(mobile): onboarding and pantry setup`.

---

### Task 32: Mobile tabs: Today, Week, Pantry, Meals, More

**Files:**
- Create: `app/(tabs)/_layout.tsx`, `app/(tabs)/{today,week,pantry}.tsx`, `app/(tabs)/meals/{index,new,[id]}.tsx`, `app/(tabs)/more/{index,shopping,household,profile}.tsx`, `src/components/plan/{PlanEntryCard,CoverageLine,SwapSheet,FeedbackBar,JobBanner,ViewToggle}.tsx`, `src/components/pantry/CategorySection.tsx`, `src/components/meals/{MealList,MealForm}.tsx`, `src/components/household/{MemberList,InviteCode,JoinForm,SlotsEditor,ScheduleForm}.tsx`, `__tests__/plan-entry-card.test.tsx`

- [ ] **Step 1: Failing test:** `PlanEntryCard` renders meal name, reason and variations; pressing "Cooked it" calls `onFeedback("cooked")`. **Step 2: Run** → FAIL. **Step 3: Implement** every screen per LLD §9.4/§9.5 using the shared hooks; Week as a horizontal day pager; swap and feedback via bottom sheets (`@gorhom/bottom-sheet` or a plain `Modal`). Touch targets ≥ 44px. **Step 4: Run** → PASS; walk through the full first-run on a device with the local API (use the machine's LAN IP in `EXPO_PUBLIC_API_URL`). **Step 5: Commit** `feat(mobile): main tabs`.

---

# Phase 12 — Deployment and verification

### Task 33: Dockerfile, Render blueprint, CI and deployment guide

**Files:**
- Create: `apps/api/Dockerfile` (LLD §11), `render.yaml` (LLD §11), `.github/workflows/ci.yml` (LLD §10.4), `docs/DEPLOYMENT.md`
- Modify: `README.md` (link to deployment guide)

- [ ] **Step 1: Build and run the image locally**
```bash
docker build -t larder-api apps/api
docker run --rm -p 8000:8000 -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@host.docker.internal:5433/larder_test -e LLM_PROVIDER=fake -e SCHEDULER_SECRET=x -e APP_ENV=production larder-api
curl -s localhost:8000/api/v1/health
```
Expected: `{"status":"ok","database":"ok","llm_provider":"fake"}`.

- [ ] **Step 2: Write `docs/DEPLOYMENT.md`** with numbered steps: create Supabase project (auth provider, pooler URL, JWT mode); create Render Blueprint from `render.yaml` and set `DATABASE_URL`, `SUPABASE_URL`, `CORS_ORIGINS`, `API_URL`; add `GROQ_API_KEY` when available (no redeploy needed beyond restart; `LLM_PROVIDER` auto-switches to `groq`); create the Vercel project with root `apps/web` and the three env vars; run `pnpm gen` against the deployed API URL before building the web app in CI (or commit the schema); mobile: `eas build --profile preview` with `EXPO_PUBLIC_*` in `eas.json`.

- [ ] **Step 3: Push CI** and confirm both jobs are green on GitHub Actions.

- [ ] **Step 4: Commit** `chore: deployment artefacts and ci`.

---

### Task 34: Final verification

- [ ] **Step 1: API** `cd apps/api && uv run ruff check && uv run pytest -q` → all green; coverage report `uv run pytest --cov=larder --cov-report=term-missing` ≥ 85% on `services`, `agents`, `routers`.
- [ ] **Step 2: JS** `pnpm typecheck && pnpm lint && pnpm test` → green.
- [ ] **Step 3: E2E** `pnpm --filter web e2e` → green.
- [ ] **Step 4: Real LLM smoke** (only if a key exists): set `GROQ_API_KEY`, restart the API, run the onboarding and one week plan manually; check `plan_jobs.model_name = 'openai/gpt-oss-120b'`, `attempts ≤ 2`, `used_fallback = false` for a household with a populated pantry. Record the observed latency in `docs/DEPLOYMENT.md`.
- [ ] **Step 5: Visual review** against LLD §9.2 on web (light and dark) and on a phone; fix deviations.
- [ ] **Step 6: Tag** `git tag v1.0.0-poc`.

---

## Self-review checklist (run after writing code for each phase)

1. **Spec coverage:** every LLD endpoint (§6) has a router test; every hard rule in §8.2 has a validator test; every screen in §9.4/§9.5 exists.
2. **Placeholder scan:** no `TODO`, no stubbed handlers returning fixed data outside `FakeLLM`.
3. **Type consistency:** names in this plan match LLD: `normalize_name`, `ingredient_matches_pantry`, `compute_inputs_hash`, `active_scopes`, `run_planner`, `run_tick`, `createApi`, `useJob`, `PlanEntryCard`, `WidgetRenderer`.
4. **Fake parity:** every schema passed to `complete_structured` has a default fake handler, so a fresh clone with `LLM_PROVIDER=fake` completes the whole first-run flow.
