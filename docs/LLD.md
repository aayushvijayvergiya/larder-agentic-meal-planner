# Larder — Low-Level Design (LLD)

**Status:** Approved design, 2026-09-18
**Reads with:** `docs/HLD.md` (why), `docs/IMPLEMENTATION_PLAN.md` (in what order)

This document is the **source of truth for every contract**: file layout, environment variables, database schema, API request/response shapes, agent state and prompts, validation rules, screen specifications, design tokens and tests. When the implementation plan and this document disagree, this document wins; fix the plan.

Conventions used below:
- Python examples are Pydantic v2 / SQLAlchemy 2.0 style. TypeScript examples are strict TS.
- `uuid` means PostgreSQL `uuid`; timestamps are `timestamptz` in UTC; dates are `date`.
- "normalised name" means the output of `normalize_name()` in §7.1.

---

## 1. Repository layout

```
larder/                              # monorepo root (this folder)
├── package.json                     # pnpm workspace root; scripts: dev, build, lint, test, typecheck, gen
├── pnpm-workspace.yaml              # packages: apps/*, packages/*
├── turbo.json                       # pipelines: build, lint, test, typecheck (dependsOn ^build)
├── render.yaml                      # Render blueprint: api web service + scheduler cron
├── .github/workflows/ci.yml         # api (uv, ruff, pytest+postgres) and js (pnpm lint/typecheck/test)
├── .gitignore  .editorconfig  .nvmrc (22)  README.md  .env.example
├── docs/                            # Requirements.md, HLD.md, LLD.md, IMPLEMENTATION_PLAN.md
├── apps/
│   ├── api/                         # Python 3.12, FastAPI, LangGraph
│   │   ├── pyproject.toml           # managed by uv; [project] name "larder"
│   │   ├── uv.lock
│   │   ├── Dockerfile
│   │   ├── alembic.ini
│   │   ├── alembic/                 # env.py (async), versions/
│   │   ├── src/larder/              # package (see §2.1)
│   │   └── tests/                   # conftest.py, unit/, agents/, integration/
│   ├── web/                         # Next.js App Router
│   │   ├── package.json  next.config.ts  tsconfig.json  postcss.config.mjs
│   │   ├── src/app/                 # routes (see §9.4)
│   │   ├── src/components/          # ui/, onboarding/, plan/, pantry/, meals/, household/
│   │   ├── src/lib/                 # supabase/{client.ts,server.ts,middleware.ts}, api.ts, theme.ts
│   │   ├── src/styles/globals.css   # tokens as CSS variables (from design-tokens), Tailwind v4 @theme
│   │   ├── tests/                   # vitest component tests
│   │   └── e2e/                     # playwright specs
│   └── mobile/                      # Expo, Expo Router
│       ├── package.json  app.json  tsconfig.json  babel.config.js
│       ├── app/                     # routes (see §9.5)
│       ├── src/components/          # mirrors web component names
│       ├── src/lib/                 # supabase.ts, api.ts, theme.tsx
│       └── __tests__/               # jest-expo
└── packages/
    ├── api-client/                  # TS: generated OpenAPI types, fetch client, TanStack Query hooks
    │   ├── package.json  tsconfig.json
    │   ├── scripts/gen.sh           # openapi-typescript from ${API_URL:-http://localhost:8000}/openapi.json
    │   └── src/{schema.d.ts, client.ts, hooks/*.ts, index.ts}
    └── design-tokens/               # TS: colors, type, spacing, radii for light and dark
        ├── package.json  tsconfig.json
        └── src/{tokens.ts, css.ts, index.ts}
```

Tooling versions (floors): Node 22 LTS, pnpm 10, Turborepo 2, Python 3.12, uv 0.5+, FastAPI 0.115+, SQLAlchemy 2.0+, Pydantic 2.9+, LangGraph 0.4+ (or 1.x), langgraph-checkpoint-postgres 2.0+, langchain-groq 0.3+, Next.js 15+ (App Router; if 16+ the middleware file is `proxy.ts`), Expo SDK 53+, Tailwind CSS 4, TanStack Query 5.

Root `package.json` scripts:

```json
{
  "scripts": {
    "dev": "turbo run dev",
    "build": "turbo run build",
    "lint": "turbo run lint",
    "typecheck": "turbo run typecheck",
    "test": "turbo run test",
    "gen": "pnpm --filter @larder/api-client gen",
    "api": "cd apps/api && uv run uvicorn larder.main:app --reload --port 8000",
    "api:test": "cd apps/api && uv run pytest"
  }
}
```

---

## 2. API application

### 2.1 Package layout (`apps/api/src/larder`)

```
larder/
├── main.py            create_app(): FastAPI instance, CORS, routers, exception handlers, lifespan (DB + checkpointer setup)
├── config.py          Settings (pydantic-settings), get_settings()
├── logging.py         JSON logging config, request-id middleware
├── errors.py          ApiError(code, status, message, details) + handlers producing the error envelope
├── db/
│   ├── session.py     async engine, async_session_factory, get_session() dependency
│   ├── base.py        DeclarativeBase, TimestampMixin (created_at, updated_at)
│   └── models/        profile.py household.py pantry.py meal.py plan.py feedback.py refresh.py  (+ __init__ re-exports)
├── auth/
│   ├── jwt.py         verify_token(token) -> TokenClaims (JWKS ES256/RS256, optional HS256)
│   └── deps.py        get_current_user() -> CurrentUser (JIT profile provisioning), get_current_household(), require_owner()
├── llm/
│   ├── base.py        LLM Protocol, LLMError
│   ├── groq.py         GroqLLM (langchain-groq ChatGroq, base_url https://api.groq.com/openai/v1)
│   ├── fake.py        FakeLLM (deterministic canned outputs keyed by schema)
│   └── factory.py     get_llm(settings) -> LLM
├── agents/
│   ├── onboarding/    fields.py state.py widgets.py prompts.py graph.py
│   ├── planner/       state.py context.py shortlist.py prompts.py validate.py fallback.py persist.py graph.py
│   ├── enrichment/    schemas.py prompts.py enrich.py
│   └── categorize/    keyword_map.py categorize.py
├── services/
│   ├── normalize.py   normalize_name(), tokens(), ingredient_matches_pantry()
│   ├── hashing.py     compute_inputs_hash()
│   ├── profiles.py    get_or_create_profile(), update_profile()
│   ├── households.py  create_implicit_household(), generate_invite(), join_by_code(), remove_member(), set_preferred_view(), update_household(), active_scopes()
│   ├── pantry.py      list_grouped(), add_items(), update_item(), delete_item()
│   ├── meals.py       create_meal(), list_meals(), update_meal(), delete_meal(), add_feedback()
│   ├── plans.py       get_current_plan(), request_generation(), request_swap(), get_job()
│   ├── shopping.py    build_shopping_list()
│   ├── unused.py      unused_pantry_items()
│   └── scheduler.py   run_tick(now_utc) -> TickReport
├── jobs/
│   └── runner.py      enqueue(job_id, background_tasks), run_job(job_id)  (in-process; single upgrade point)
├── schemas/           Pydantic API models: common.py me.py onboarding.py households.py pantry.py meals.py plans.py internal.py
└── routers/           health.py me.py onboarding.py households.py pantry.py meals.py plans.py internal.py
```

Rules: routers contain no business logic (parse → call service → return schema). Services own transactions. Agents never import routers. Models never import services.

### 2.2 Application factory

```python
# larder/main.py
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Larder API", version="1.0.0", openapi_url="/openapi.json", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    for r in (health.router, me.router, onboarding.router, households.router, pantry.router, meals.router, plans.router, internal.router):
        app.include_router(r, prefix="/api/v1")
    return app

app = create_app()
```

`lifespan` creates the async engine, runs `AsyncPostgresSaver.setup()` for the onboarding checkpointer once (idempotent), and stores `app.state.llm = get_llm(settings)` and `app.state.checkpointer`.

### 2.3 Error envelope

```json
{ "error": { "code": "validation_error", "message": "name must not be empty", "details": { "field": "name" } } }
```

| code | HTTP | When |
|------|------|------|
| `unauthorized` | 401 | Missing/invalid JWT |
| `forbidden` | 403 | Wrong household, non-owner action, bad scheduler secret |
| `not_found` | 404 | Entity missing or not visible to caller |
| `validation_error` | 422 | Pydantic or business validation failure (`details.field` when applicable) |
| `conflict` | 409 | Already in a household, duplicate pantry item, expired invite |
| `job_running` | 409 | A job for the same plan is already queued/running |
| `llm_unavailable` | 503 | Provider error after retry |
| `onboarding_incomplete` | 409 | Plan/pantry endpoints called before onboarding completes |

FastAPI's default `RequestValidationError` is converted into this envelope with `code = validation_error`.

### 2.4 Settings (`larder/config.py`)

| Variable | Type / default | Purpose |
|----------|----------------|---------|
| `APP_ENV` | `local` \| `test` \| `production`; default `local` | Logging format, docs exposure |
| `DATABASE_URL` | required; `postgresql+asyncpg://…` | SQLAlchemy. On Supabase use the **session pooler** URL (port 5432, IPv4) |
| `CHECKPOINT_DATABASE_URL` | optional; default derived from `DATABASE_URL` by replacing `postgresql+asyncpg://` with `postgresql://` | psycopg URL for the LangGraph checkpointer |
| `SUPABASE_URL` | required in production | Base URL; JWKS at `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` |
| `SUPABASE_JWT_SECRET` | optional | HS256 fallback for legacy projects; also used by tests to mint tokens |
| `SUPABASE_ANON_KEY` | optional | Sent as the `apikey` header when fetching JWKS; required by the local Supabase gateway, ignored by hosted projects |
| `AUTH_MODE` | `jwks` \| `hs256`; default `jwks` | Tests set `hs256` |
| `JWT_AUDIENCE` | default `authenticated` | |
| `LLM_PROVIDER` | `groq` \| `fake`; default `fake` if `GROQ_API_KEY` empty else `groq` | |
| `GROQ_API_KEY` | optional | Added after development |
| `GROQ_BASE_URL` | default `https://api.groq.com/openai/v1` | |
| `GROQ_MODEL` | default `openai/gpt-oss-120b` | Any Groq-hosted chat model with tool use; structured-output models preferred (see §5.2) |
| `LLM_TIMEOUT_SECONDS` | default `60` | |
| `SCHEDULER_SECRET` | required in production | `X-Scheduler-Secret` header value |
| `CORS_ORIGINS` | comma-separated; default `http://localhost:3000` | |
| `PLAN_HISTORY_WEEKS` | default `8` | Older superseded plans are deleted by the tick |

`get_settings()` is `functools.lru_cache`d; tests call `get_settings.cache_clear()` after setting env vars.

---

## 3. Database schema

Managed by Alembic (`alembic/versions/0001_initial.py` creates everything below in one migration; later migrations add columns). All tables have `created_at timestamptz not null default now()` and, where marked, `updated_at` maintained by the ORM.

### 3.1 Enumerations (PostgreSQL enums, names as given)

```
sex_enum:            female | male | other | prefer_not_to_say
activity_enum:       sedentary | light | moderate | active | very_active
diet_enum:           omnivore | vegetarian | eggetarian | vegan | pescatarian | jain | other
skill_enum:          beginner | intermediate | advanced
onboarding_enum:     pending | in_progress | complete
member_role_enum:    owner | member
view_enum:           single | family
pantry_category_enum: spices | grains | pulses | flours | dairy | vegetables | fruits | proteins | condiments | oils | snacks | beverages | frozen | other
meal_source_enum:    user | generated
enrichment_enum:     pending | complete | failed
plan_scope_enum:     family | single
plan_status_enum:    active | superseded
job_mode_enum:       week | today | slot
job_status_enum:     queued | running | ready | failed
job_origin_enum:     user | scheduler | onboarding
feedback_enum:       up | down | cooked | skipped
refresh_kind_enum:   weekly | daily
```

### 3.2 Tables

**profiles** — one row per auth user; `id` equals Supabase `auth.users.id`.

| column | type | notes |
|--------|------|-------|
| id | uuid PK | from JWT `sub` |
| email | text not null | from JWT |
| display_name | text | |
| date_of_birth | date | |
| sex | sex_enum | |
| height_cm | smallint | 50–250 |
| weight_kg | numeric(5,1) | 20–400 |
| activity_level | activity_enum | |
| diet_type | diet_enum | |
| cuisines | text[] not null default '{}' | e.g. `{north_indian, gujarati, continental}` free slugs |
| allergens | text[] not null default '{}' | normalised names, e.g. `{peanut, shellfish}` |
| dislikes | text[] not null default '{}' | normalised ingredient/dish names |
| likes | text[] not null default '{}' | |
| medical_conditions | jsonb not null default '[]' | `[{"name": "type 2 diabetes", "notes": "avoid refined sugar"}]` |
| medical_notes | text | free text |
| goals | text[] not null default '{}' | `weight_loss, muscle_gain, maintenance, manage_condition, eat_healthier, save_time, reduce_waste` |
| cooking_skill | skill_enum | |
| max_prep_minutes | smallint | 5–240 |
| onboarding_status | onboarding_enum not null default 'pending' | |
| onboarding_thread_id | text | LangGraph thread id |
| created_at, updated_at | timestamptz | |

**households**

| column | type | notes |
|--------|------|-------|
| id | uuid PK default gen_random_uuid() | |
| name | text not null | default `"{display_name}'s kitchen"` for implicit |
| owner_id | uuid not null FK profiles(id) | |
| timezone | text not null default 'Asia/Kolkata' | IANA name; validated with `zoneinfo` |
| slots | jsonb not null | `[{"key":"breakfast","label":"Breakfast","order":1}, …]` default four slots: breakfast, lunch, snack, dinner |
| weekly_refresh_day | smallint not null default 6 | 0 = Monday … 6 = Sunday |
| weekly_refresh_time | time not null default '18:00' | local |
| daily_refresh_time | time not null default '06:00' | local |
| is_implicit | boolean not null default false | auto-created solo household |
| created_at, updated_at | | |

**household_members**

| column | type | notes |
|--------|------|-------|
| household_id | uuid FK households(id) on delete cascade | |
| user_id | uuid FK profiles(id) on delete cascade | |
| role | member_role_enum not null | |
| preferred_view | view_enum not null default 'family' | set to `single` when household is implicit |
| joined_at | timestamptz not null default now() | |
| PK (household_id, user_id); UNIQUE (user_id) | | enforces one household per user |

**household_invites**

| column | type | notes |
|--------|------|-------|
| id | uuid PK | |
| household_id | uuid FK | |
| code | text not null UNIQUE | 8 chars from `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` |
| created_by | uuid FK profiles | |
| expires_at | timestamptz not null | default now() + 7 days |
| max_uses | smallint not null default 10 | |
| uses | smallint not null default 0 | |
| revoked_at | timestamptz | |

**pantry_items**

| column | type | notes |
|--------|------|-------|
| id | uuid PK | |
| household_id | uuid FK | |
| name | text not null | display, as typed (trimmed) |
| normalized_name | text not null | |
| category | pantry_category_enum not null | |
| is_available | boolean not null default true | "ran out" toggle keeps the row |
| added_by | uuid FK profiles | |
| created_at, updated_at | | |
| UNIQUE (household_id, normalized_name); INDEX (household_id, category) | | |

**meals**

| column | type | notes |
|--------|------|-------|
| id | uuid PK | |
| household_id | uuid FK | |
| name | text not null | |
| normalized_name | text not null | |
| description | text | one or two sentences |
| cuisine | text | slug, e.g. `south_indian` |
| meal_types | text[] not null default '{}' | subset of household slot keys plus `any` |
| diet_tags | text[] not null default '{}' | from `{vegan, vegetarian, eggetarian, pescatarian, jain, contains_meat, gluten_free, dairy_free, nut_free, low_carb, high_protein}` |
| allergens | text[] not null default '{}' | from §7.3 allergen vocabulary |
| prep_minutes | smallint | |
| instructions | text | optional steps, markdown |
| source | meal_source_enum not null | |
| created_by | uuid FK profiles | null for generated |
| enrichment_status | enrichment_enum not null default 'pending' | |
| created_at, updated_at | | |
| INDEX (household_id, source); UNIQUE (household_id, normalized_name) | | generated duplicates are reused |

**meal_ingredients**

| column | type | notes |
|--------|------|-------|
| id | uuid PK | |
| meal_id | uuid FK meals on delete cascade | |
| name | text not null | |
| normalized_name | text not null | |
| category | pantry_category_enum not null | |
| is_staple | boolean not null default false | salt, oil, water, sugar, common spices: excluded from coverage and shopping |
| is_optional | boolean not null default false | excluded from shopping |
| position | smallint not null | ordering |
| UNIQUE (meal_id, normalized_name) | | |

**meal_plans**

| column | type | notes |
|--------|------|-------|
| id | uuid PK | |
| household_id | uuid FK | |
| scope | plan_scope_enum not null | |
| member_id | uuid FK profiles | required when scope = single, null otherwise |
| start_date | date not null | |
| end_date | date not null | ≤ start_date + 6; exactly start_date + 6 except for scheduler gap-fill plans (§7.5) |
| status | plan_status_enum not null default 'active' | |
| created_at, updated_at | | |
| INDEX (household_id, scope, member_id, status, start_date) | | Service guarantees one *active* plan per scope whose range contains a date (overlapping plans are superseded at creation) |

**plan_entries**

| column | type | notes |
|--------|------|-------|
| id | uuid PK | |
| plan_id | uuid FK meal_plans on delete cascade | |
| date | date not null | |
| slot_key | text not null | |
| meal_id | uuid FK meals | |
| reason | text not null | one sentence from the planner |
| covered_ingredients | text[] not null default '{}' | normalised names on hand |
| missing_ingredients | jsonb not null default '[]' | `[{"name","category","is_optional"}]` non-staple only |
| generated_at | timestamptz not null | |
| UNIQUE (plan_id, date, slot_key) | | |

**plan_entry_variations**

| column | type | notes |
|--------|------|-------|
| id | uuid PK | |
| plan_entry_id | uuid FK on delete cascade | |
| member_id | uuid FK profiles | |
| note | text not null | e.g. "skip green chilli" |
| UNIQUE (plan_entry_id, member_id) | | |

**plan_jobs**

| column | type | notes |
|--------|------|-------|
| id | uuid PK | |
| plan_id | uuid FK meal_plans on delete cascade | |
| mode | job_mode_enum not null | |
| origin | job_origin_enum not null | |
| target_date | date | today/slot modes |
| target_slot_key | text | slot mode |
| target_entry_id | uuid | slot mode |
| swap_reason | text | slot mode, user supplied |
| status | job_status_enum not null default 'queued' | |
| inputs_hash | text | computed at `load_context` |
| model_name | text | |
| attempts | smallint not null default 0 | repair attempts used |
| used_fallback | boolean not null default false | |
| error | text | |
| created_at, started_at, finished_at | timestamptz | |
| INDEX (plan_id, status) | | |

**meal_feedback**

| column | type | notes |
|--------|------|-------|
| id | uuid PK | |
| household_id | uuid FK | |
| member_id | uuid FK profiles | |
| meal_id | uuid FK meals on delete cascade | |
| plan_entry_id | uuid FK plan_entries on delete set null | |
| kind | feedback_enum not null | |
| comment | text | ≤ 280 chars |
| created_at | | |
| INDEX (household_id, meal_id) | | `up`/`down` from the same member on the same meal replace the previous up/down (service rule); `cooked`/`skipped` append |

**refresh_runs**

| column | type | notes |
|--------|------|-------|
| id | uuid PK | |
| household_id | uuid FK | |
| kind | refresh_kind_enum not null | |
| period_key | text not null | weekly: ISO year-week of local date, e.g. `2026-W38`; daily: local date `2026-09-18` |
| ran_at | timestamptz not null | |
| result | jsonb not null | `{"enqueued": [job_id…], "skipped_reason": null}` |
| UNIQUE (household_id, kind, period_key) | | idempotency |

**LangGraph checkpoint tables** (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`) are created by `AsyncPostgresSaver.setup()` at start-up, not by Alembic; Alembic's `env.py` lists them in `include_object` exclusions so autogenerate ignores them.

---

## 4. Authentication and authorisation

### 4.1 Token verification (`auth/jwt.py`)

```python
@dataclass(frozen=True)
class TokenClaims:
    sub: uuid.UUID
    email: str

def verify_token(token: str, settings: Settings) -> TokenClaims:
    if settings.auth_mode == "hs256":
        payload = jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], audience=settings.jwt_audience)
    else:
        jwks = PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json", cache_keys=True)
        key = jwks.get_signing_key_from_jwt(token)
        payload = jwt.decode(token, key.key, algorithms=["ES256", "RS256"], audience=settings.jwt_audience)
    return TokenClaims(sub=uuid.UUID(payload["sub"]), email=payload.get("email", ""))
```

Any `jwt.PyJWTError` → `ApiError("unauthorized", 401)`.

### 4.2 Dependencies (`auth/deps.py`)

```python
@dataclass
class CurrentUser:
    profile: Profile
    household: Household | None      # None only before onboarding completes
    membership: HouseholdMember | None

async def get_current_user(authorization: str = Header(...), session=Depends(get_session), settings=Depends(get_settings)) -> CurrentUser
async def require_household(user=Depends(get_current_user)) -> CurrentUser      # 409 onboarding_incomplete if no household
async def require_owner(user=Depends(require_household)) -> CurrentUser         # 403 if role != owner
```

`get_current_user` calls `profiles.get_or_create_profile(session, claims)` (insert on first sight, `ON CONFLICT DO NOTHING`, then select). Bearer scheme only.

### 4.3 Authorisation rules

- Every household-scoped read/write filters by `user.household.id`; a mismatched id in the path is a `not_found` (never leak existence).
- Owner-only: `POST /households/{id}/invites`, `PATCH /households/{id}`, `DELETE /households/{id}/members/{user_id}` for another user.
- A member may remove themselves (leave). The owner cannot leave while other members exist; they must remove them first (409 `conflict`, message explains).
- `/internal/*` checks `X-Scheduler-Secret` with `hmac.compare_digest`.

---

## 5. LLM provider layer

### 5.1 Protocol (`llm/base.py`)

```python
T = TypeVar("T", bound=BaseModel)

class LLM(Protocol):
    name: str                                  # "groq:openai/gpt-oss-120b" or "fake"
    async def complete_text(self, *, system: str, user: str, temperature: float = 0.7) -> str: ...
    async def complete_structured(self, *, system: str, user: str, schema: type[T], temperature: float = 0.2) -> T: ...

class LLMError(Exception):
    """Raised after retry; routers map to llm_unavailable."""
```

### 5.2 `GroqLLM` (`llm/groq.py`)

- Uses the official `langchain-groq` integration: `ChatGroq(model=settings.groq_model, api_key=settings.groq_api_key, base_url=settings.groq_base_url, timeout=settings.llm_timeout_seconds, max_retries=1)`. Groq's API is OpenAI-compatible, so `ChatOpenAI(base_url=…)` from `langchain-openai` is an acceptable drop-in if `langchain-groq` lags a LangChain release.
- `complete_structured` uses `model.with_structured_output(schema, method="json_schema")`; if the model rejects `json_schema` (only some Groq models support it), fall back once to `method="function_calling"` (tool use, supported broadly). Output is validated by Pydantic; a `ValidationError` is wrapped in `LLMError`.
- Model choice: default `openai/gpt-oss-120b` (supports structured outputs and tool use on Groq). Alternatives that work through the same code path: `moonshotai/kimi-k2-instruct`, `meta-llama/llama-4-maverick-17b-128e-instruct`, `llama-3.3-70b-versatile` (tool-calling fallback only). Model ids change; check the Groq model list when deploying and set `GROQ_MODEL` accordingly.
- Rate limits: Groq free-tier keys have per-minute token and request caps. Keep every prompt compact: the planner passes at most 40 shortlist candidates as `{id, name, coverage, missing}` only, pantry as names grouped by category, and member constraints only (no free-text medical notes beyond 500 chars). On HTTP 429 the client's single retry honours `retry-after`; a second 429 becomes `LLMError` (job failed, user sees Retry).
- Logs latency and `usage_metadata` tokens when present.

### 5.3 `FakeLLM` (`llm/fake.py`)

Deterministic, no network. Behaviour:
- `complete_text` returns `f"[fake] {user[:80]}"` unless a scripted response is queued via `fake.script_text([...])`.
- `complete_structured(schema=X)` looks up a handler registered for `X.__name__`; built-in handlers exist for every schema in this document: `QuestionText`, `ParsedFieldAnswer`, `PlanDraft`, `MealEnrichment`, `CategoryAssignments`. Handlers produce **valid, constraint-respecting** data from the prompt's structured context (the user prompt always embeds a JSON block between `<context>` tags that the fake parses). Tests can override with `fake.script_structured(X, [instances...])` or `fake.fail_next(LLMError)`.
- The `PlanDraft` handler fills every requested (date, slot) from the shortlist in round-robin order, falling back to a generated meal named `"Simple {slot} bowl"` with ingredients `[rice (grains), dal (pulses), onion (vegetables)]`, `diet_tags=["vegetarian","vegan"]`, `allergens=[]`, `prep_minutes=25`.

### 5.4 Prompt conventions

Every user prompt ends with a `<context>…</context>` block containing a JSON document. System prompts state the persona, the output schema intention and the hard rules. Temperature: 0.7 for conversational text, 0.2 for structured drafts, 0 for enrichment and categorisation.

---

## 6. API contracts

Base path `/api/v1`. All bodies JSON. Times ISO-8601. Unless stated, endpoints require a Bearer token and a completed household (`require_household`).

### 6.1 Common schemas (`schemas/common.py`)

```python
class SlotDef(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,30}$")
    label: str = Field(min_length=1, max_length=40)
    order: int = Field(ge=1, le=10)

class MemberSummary(BaseModel):
    user_id: UUID; display_name: str | None; role: Literal["owner","member"]; preferred_view: Literal["single","family"]

class HouseholdOut(BaseModel):
    id: UUID; name: str; owner_id: UUID; timezone: str; slots: list[SlotDef]
    weekly_refresh_day: int; weekly_refresh_time: time; daily_refresh_time: time
    is_implicit: bool; members: list[MemberSummary]
```

### 6.2 Health

`GET /health` (no auth) → `200 {"status":"ok","database":"ok","llm_provider":"fake"}`; `503` with `"database":"error"` when the DB ping fails.

### 6.3 Me

**`GET /me`** (auth only; household optional)
```json
{ "profile": ProfileOut, "household": HouseholdOut | null, "onboarding_status": "pending|in_progress|complete" }
```
`ProfileOut` mirrors the `profiles` columns except `onboarding_thread_id`.

**`PATCH /me`** body `ProfilePatch` (all optional; same validation as onboarding fields, §8.1). Returns `ProfileOut`. Changing any planner-relevant field is picked up by the next daily refresh through the inputs hash.

### 6.4 Onboarding (auth only; allowed before household exists)

**`POST /onboarding/start`** → `200 TurnResponse`. Idempotent: if `profiles.onboarding_thread_id` exists and status is `in_progress`, returns the current pending question. If status is `complete` → `409 conflict`.

**`POST /onboarding/turn`**
```json
{ "thread_id": "…", "answer": { "kind": "widget", "value": <json> } | { "kind": "text", "text": "I'm 172cm" } }
```
→ `200 TurnResponse`:
```json
{
  "thread_id": "…",
  "message": "Lovely, Priya. Roughly how tall are you?",
  "widget": Widget | null,
  "field": "height_cm" | null,
  "draft": ProfileDraft,
  "progress": { "answered": 4, "total": 15 },
  "is_complete": false
}
```
`Widget` is a discriminated union on `type` (§8.1). When `is_complete` is true, `widget` is `{"type":"review","draft":ProfileDraft}`.

Validation failures of a widget answer return `200` with `message` explaining and the same `field` re-asked (not 422), so the conversation continues naturally.

**`POST /onboarding/complete`** body `{ "thread_id": "…", "overrides": ProfilePatch | null }` → `200 { "profile": ProfileOut, "household": HouseholdOut, "first_plan_job_id": UUID }`. Steps in one transaction: apply draft + overrides to profile, `onboarding_status = complete`, create implicit household (`name = "{display_name}'s kitchen"`, member role owner, `preferred_view = single`), then outside the transaction enqueue a `week` job (`origin = onboarding`, start today) and return its id. Idempotent if already complete (returns current state, `first_plan_job_id = null`).

### 6.5 Households

**`GET /households/me`** → `HouseholdOut`.

**`PATCH /households/{id}`** (owner) body: any of `name`, `timezone`, `slots` (1–6 unique keys), `weekly_refresh_day` (0–6), `weekly_refresh_time`, `daily_refresh_time`. Returns `HouseholdOut`. Changing `slots` marks the current active plans for regeneration by the next daily refresh (hash includes slots). Renaming clears `is_implicit`.

**`POST /households/{id}/invites`** (owner) body `{ "expires_in_days": 7, "max_uses": 10 }` (defaults) → `201 { "code": "K7PQ2M9X", "expires_at": "…", "max_uses": 10 }`. Active invites are listed by **`GET /households/{id}/invites`** and revoked by **`DELETE /households/{id}/invites/{code}`**.

**`POST /households/join`** body `{ "code": "K7PQ2M9X" }` → `200 HouseholdOut`. Rules: code must be unrevoked, unexpired, `uses < max_uses`; caller must have completed onboarding; if caller's current household is implicit and they are its only member, that household (and its pantry, meals, plans) is deleted; if the caller is in a non-implicit household → `409 conflict` "Leave your current household first"; on success `uses += 1`, membership role `member`, `preferred_view = family`.

**`DELETE /households/{id}/members/{user_id}`** → `204`. Owner removes anyone; a member may pass their own id to leave. The removed user gets a fresh implicit household (`preferred_view = single`) and a `week` job is enqueued for it.

**`PATCH /households/{id}/members/me`** body `{ "preferred_view": "single" | "family" }` → `MemberSummary`. In a one-member household only `single` is accepted.

### 6.6 Pantry

**`GET /pantry`** → 
```json
{ "categories": [ { "category": "vegetables", "label": "Vegetables", "items": [ PantryItemOut ] } ], "total": 42 }
```
Categories ordered by the canonical order in §3.1; empty categories omitted. `PantryItemOut = { id, name, category, is_available, updated_at }`.

**`POST /pantry/items`** body `{ "items": [ { "name": "paneer", "category": "dairy" | null } ] }` (1–100 items) → `201 { "created": [PantryItemOut], "existing": [PantryItemOut] }`. Names are trimmed; duplicates (by normalised name) within the request are collapsed; names already present are returned in `existing` and, if they were `is_available = false`, flipped back to available. Missing categories are filled by the categoriser (§8.4).

**`PATCH /pantry/items/{id}`** body any of `name`, `category`, `is_available` → `PantryItemOut`. **`DELETE /pantry/items/{id}`** → `204`.

**`GET /pantry/suggestions`** → `{ "items": [ { "name": "onion", "category": "vegetables" }, … ] }`: a static list of ~60 common staples per cuisine cluster (from `keyword_map.py`), minus items already in the pantry. Used by the pantry setup screen chips.

### 6.7 Meals

**`GET /meals?query=&meal_type=&source=user|generated|all`** (default `user`) → `{ "meals": [MealOut] }` ordered by name, max 500. `MealOut`:
```json
{ "id", "name", "description", "cuisine", "meal_types", "diet_tags", "allergens", "prep_minutes", "instructions", "source", "enrichment_status",
  "ingredients": [ { "name", "category", "is_staple", "is_optional" } ],
  "feedback": { "up": 3, "down": 0, "cooked": 2, "last_cooked_at": "…" | null } }
```

**`POST /meals`** body `{ "name": "Palak paneer", "description"?: str, "ingredients"?: [str], "instructions"?: str }` → `201 MealOut`. Runs enrichment synchronously (§8.3); on `LLMError` the meal is saved with `enrichment_status = failed`, the raw ingredient strings stored with category `other`, and a `202`-style body is **not** used; the client shows a "Couldn't enrich; you can edit the details" note based on `enrichment_status`. Duplicate normalised name → `409 conflict`.

**`POST /meals/{id}/enrich`** → re-runs enrichment on demand; returns `MealOut`.

**`PATCH /meals/{id}`** body: any `MealOut` editable field including a full `ingredients` list (replace semantics). Only `source = user` meals are editable; generated meals return `403 forbidden`.

**`DELETE /meals/{id}`** → `204`. Deletion is refused with `409 conflict` ("This meal is in your current plan") if any `active` plan has an entry referencing the meal; otherwise the row is hard-deleted (ingredients and feedback cascade).

**`POST /meals/{id}/feedback`** body `{ "kind": "up|down|cooked|skipped", "plan_entry_id"?: UUID, "comment"?: str }` → `201 { "feedback": {up, down, cooked, last_cooked_at} }`.

### 6.8 Plans

**`GET /plans/current?scope=family|single&date=YYYY-MM-DD`** (`date` defaults to household-local today; `scope` defaults to the caller's `preferred_view`) →
```json
{
  "plan": {
    "id", "scope", "member_id", "start_date", "end_date",
    "days": [ { "date": "2026-09-18", "entries": [ PlanEntryOut ] } ],
    "coverage": { "on_hand": 31, "needed": 40 },
    "unused_pantry": [ { "name": "bottle gourd", "category": "vegetables" } ]
  } | null,
  "active_job": { "id", "mode", "status", "created_at" } | null
}
```
`PlanEntryOut`:
```json
{ "id", "date", "slot_key", "slot_label", "meal": MealOut, "reason": "Uses the spinach and paneer you already have.",
  "covered_ingredients": ["spinach","paneer"], "missing_ingredients": [ { "name":"cream", "category":"dairy", "is_optional": true } ],
  "variations": [ { "member_id", "display_name", "note" } ],
  "my_feedback": "up" | "down" | null, "cooked_count": 1 }
```
`days` covers `start_date..end_date` with entries sorted by slot order.

**`POST /plans/generate`** body `{ "scope": "family|single", "mode": "week|today", "date"?: "YYYY-MM-DD" }` → `202 { "job_id", "plan_id" }`.
- `week`: `start = date or today`; any active plan of the same scope overlapping `[start, start+6]` is set `superseded`; a new plan row is created; job enqueued.
- `today`: requires an active plan containing `date`; enqueues a job for that plan/date.
- `409 job_running` if a queued/running job exists for the plan. `409 validation_error` if `scope = family` in a one-member household.

**`POST /plans/{plan_id}/entries/{entry_id}/swap`** body `{ "reason"?: "too heavy for a weeknight" }` → `202 { "job_id" }` (slot mode).

**`GET /plans/jobs/{job_id}`** → `{ "id", "plan_id", "mode", "status", "error", "created_at", "started_at", "finished_at" }`.

**`GET /plans/{plan_id}/shopping-list`** →
```json
{ "from_date": "2026-09-18", "to_date": "2026-09-24",
  "groups": [ { "category": "dairy", "label": "Dairy", "items": [ { "name": "cream", "meals": ["Palak paneer"] } ] } ], "total": 7 }
```

### 6.9 Internal

**`POST /internal/scheduler/tick`** header `X-Scheduler-Secret` → `200 TickReport`:
```json
{ "ran_at": "…", "households_checked": 12, "weekly_enqueued": ["job…"], "daily_enqueued": ["job…"], "skipped": 10, "cleaned_plans": 2 }
```

---

## 7. Services

### 7.1 Normalisation (`services/normalize.py`)

```python
_STOP = {"fresh", "chopped", "sliced", "diced", "ground", "whole", "large", "small", "medium", "cup", "cups", "tbsp", "tsp", "of", "a", "the"}

def normalize_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    words = [w for w in s.split() if w not in _STOP]
    words = [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words]   # naive singular
    return " ".join(words)

def tokens(s: str) -> set[str]: return set(normalize_name(s).split())

def ingredient_matches_pantry(ingredient_norm: str, pantry_norms: set[str]) -> str | None:
    """Exact match first; otherwise the pantry item whose tokens are a subset of the ingredient tokens (longest wins)."""
```

Examples: `"Fresh Spinach leaves"` → `"spinach leaf"`; `"Paneer cubes"` matches pantry `"paneer"`; `"tomatoes"` → `"tomato"`.

### 7.2 Coverage

For a meal: `countable = [i for i in ingredients if not i.is_staple]`; `covered = [i for i in countable if ingredient_matches_pantry(i.normalized_name, pantry)]`; `coverage = len(covered)/len(countable)` (1.0 if `countable` is empty). `missing = [i for i in countable if not covered]` including optional ones flagged.

### 7.3 Vocabularies (`agents/planner/vocab.py`)

- Allergens: `peanut, tree_nut, dairy, egg, gluten, soy, sesame, shellfish, fish, mustard, sulphite`.
- Diet compatibility: a meal satisfies a member's `diet_type` when its `diet_tags` include one of:

| diet_type | acceptable diet_tags |
|-----------|----------------------|
| vegan | vegan |
| vegetarian | vegan, vegetarian |
| eggetarian | vegan, vegetarian, eggetarian |
| jain | jain |
| pescatarian | vegan, vegetarian, eggetarian, pescatarian |
| omnivore, other | any |

Family scope uses the strictest member: the meal must satisfy **every** member's diet type.

- Medical restrictions map (`medical_rules.py`): condition name keywords → forbidden ingredient tokens or required tags. v1 rules: `diabet*` → soft-avoid `{sugar, jaggery, honey, white bread, maida}` and require no `diet_tags` conflict; `hypertension|blood pressure` → soft-avoid `{pickle, papad, processed meat}`; `celiac|gluten` → hard allergen `gluten`; `lactose` → hard allergen `dairy`; `gout` → soft-avoid `{organ meat, shellfish}`; `kidney|ckd` → soft-avoid `{banana, potato skin, tomato ketchup}`. Hard rules become violations; soft rules become warnings and prompt text.

### 7.4 Inputs hash (`services/hashing.py`)

```python
def compute_inputs_hash(ctx: PlanningContext) -> str:
    payload = {
        "pantry": sorted(p.normalized_name for p in ctx.pantry if p.is_available),
        "members": [ {"id": str(m.id), "diet": m.diet_type, "allergens": sorted(m.allergens), "dislikes": sorted(m.dislikes),
                      "likes": sorted(m.likes), "cuisines": sorted(m.cuisines), "medical": sorted(c["name"] for c in m.medical_conditions),
                      "max_prep": m.max_prep_minutes, "goals": sorted(m.goals)} for m in sorted(ctx.members, key=lambda m: str(m.id)) ],
        "slots": [s.key for s in ctx.slots],
        "library_version": ctx.library_count_and_max_updated,   # "42:2026-09-17T10:00:00Z"
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
```

Feedback is deliberately excluded (feedback influences the next scheduled generation but does not trigger one).

### 7.5 Scheduler (`services/scheduler.py`)

```python
async def run_tick(session, now_utc: datetime, enqueue: Callable[[UUID], Awaitable[None]]) -> TickReport
```
Per household, with `local = now_utc.astimezone(ZoneInfo(h.timezone))`:
1. **Weekly**: due if `local.weekday() == h.weekly_refresh_day and local.time() >= h.weekly_refresh_time`. `period_key = f"{iso_year}-W{iso_week:02d}"` of `local.date()`. If no `refresh_runs` row for (h, weekly, period_key): for each active scope, create a plan with `start_date = local.date() + 1 day` (superseding overlaps) and a `week` job with `origin = scheduler`; insert the run row. Insert first with `ON CONFLICT DO NOTHING`; if it did not insert, skip (protects against concurrent ticks).
2. **Daily** (always evaluated *after* the weekly step in the same tick): due if `local.time() >= h.daily_refresh_time`; `period_key = local.date().isoformat()`. If no run: for each active scope, find the active plan containing `local.date()`; if none → create a **gap-fill** plan: `start_date = today`, `end_date = min(today + 6, next_plan.start_date - 1)` where `next_plan` is the earliest active plan of the same scope starting after today (if there is none, `end_date = today + 6`), and enqueue a `week` job for it; else compute `compute_inputs_hash(load_context(...))` and compare with the plan's latest `ready` job hash; if different → `today` job for `local.date()`; else record `skipped_reason = "unchanged"`. A gap-fill plan never supersedes a future plan.
3. **Cleanup**: delete `superseded` plans with `end_date < local.date() - PLAN_HISTORY_WEEKS*7`.
4. Never enqueue when a queued/running job already exists for the plan.

`active_scopes(household)` → `[("family", None)]` if `len(members) > 1 and any(m.preferred_view == "family")` plus `[("single", m.id) for m in members if m.preferred_view == "single"]`; a one-member household yields exactly `[("single", member.id)]`.

### 7.6 Job runner (`jobs/runner.py`)

```python
async def enqueue(job_id: UUID, background: BackgroundTasks) -> None: background.add_task(run_job, job_id)
async def run_job(job_id: UUID) -> None:
    # own session; set status running/started_at; build PlannerInput from job; invoke planner graph;
    # on success status ready + finished_at; on exception status failed + error (str, ≤ 2000 chars); always log.
```
Scheduler-originated jobs are enqueued via the same function using the request's `BackgroundTasks`. This file is the single place to swap in a queue later.

### 7.7 Shopping list (`services/shopping.py`)

```python
def build_shopping_list(entries: list[PlanEntry], meals_by_id: dict[UUID, Meal], from_date: date) -> ShoppingList
```
Take entries with `date >= from_date`; flatten `missing_ingredients`; drop `is_optional`; dedupe by normalised name keeping the first display name; attach the list of meal names; group by category in canonical order; sort items alphabetically.

### 7.8 Unused pantry (`services/unused.py`)

`unused_pantry_items(pantry, entries, meals_by_id)` → available pantry items (excluding categories `spices, condiments, oils`) whose normalised name is not in any entry's `covered_ingredients` for dates ≥ today, max 8, alphabetical.

---

## 8. Agents

### 8.1 Onboarding agent

**Fields (`agents/onboarding/fields.py`)** — ordered; each has a widget spec and a validator.

| # | field | widget | validation |
|---|-------|--------|------------|
| 1 | display_name | `text` (max 40) | non-empty |
| 2 | date_of_birth | `date` (min 1900-01-01, max today−5y) | age 5–120 |
| 3 | sex | `single_select` options female/male/other/prefer_not_to_say | enum |
| 4 | height_cm | `number` unit cm min 50 max 250 step 1 | range |
| 5 | weight_kg | `number` unit kg min 20 max 400 step 0.5 | range |
| 6 | activity_level | `single_select` 5 options with descriptions | enum |
| 7 | diet_type | `single_select` 7 options | enum |
| 8 | cuisines | `multi_select` options `north_indian, south_indian, gujarati, bengali, punjabi, maharashtrian, continental, italian, chinese, mediterranean, mexican, thai` allow_custom | 1–6 slugs |
| 9 | allergens | `multi_select` allergen vocabulary + "none" allow_custom | list |
| 10 | dislikes | `chips` free entry, placeholder "e.g. bitter gourd, mushrooms" | 0–20 |
| 11 | likes | `chips` | 0–20 |
| 12 | medical_conditions | `chips` with common suggestions (`type 2 diabetes, hypertension, high cholesterol, PCOS, thyroid, celiac disease, lactose intolerance`) + "none" | list |
| 12b | medical_notes | `text` multiline, only if 12 non-empty | ≤ 500 chars |
| 13 | goals | `multi_select` 7 goal slugs | 1–4 |
| 14 | cooking_skill | `single_select` | enum |
| 15 | max_prep_minutes | `single_select` 15/30/45/60/90 | enum values |

**Widget schema (`widgets.py`)** — discriminated union on `type`:

```python
class TextWidget(BaseModel):        type: Literal["text"]; placeholder: str = ""; multiline: bool = False; max_length: int = 200
class NumberWidget(BaseModel):      type: Literal["number"]; unit: str; min: float; max: float; step: float = 1
class DateWidget(BaseModel):        type: Literal["date"]; min: date; max: date
class Option(BaseModel):            value: str; label: str; description: str | None = None
class SingleSelectWidget(BaseModel):type: Literal["single_select"]; options: list[Option]
class MultiSelectWidget(BaseModel): type: Literal["multi_select"]; options: list[Option]; allow_custom: bool = False; min: int = 0; max: int = 20
class ChipsWidget(BaseModel):       type: Literal["chips"]; suggestions: list[str] = []; placeholder: str = ""; max: int = 20
class ReviewWidget(BaseModel):      type: Literal["review"]; draft: ProfileDraft
Widget = Annotated[Union[...], Field(discriminator="type")]
```

Answer `value` types: text → `str`; number → `float`; date → `"YYYY-MM-DD"`; single_select → `str`; multi_select/chips → `list[str]`.

**State (`state.py`)**

```python
class OnboardingState(TypedDict):
    user_id: str
    draft: dict                     # ProfileDraft as dict (partial)
    current_field: str | None
    last_answer: dict | None        # {"kind": "widget"|"text", "value"/"text": ...}
    message: str                    # assistant text for this turn
    error: str | None               # validation message to include
    history: list[dict]             # [{"role": "assistant"|"user", "content": str}] capped at 20
    is_complete: bool
```

**Graph (`graph.py`)**

```
START → ingest_answer → select_next_field → (has field?) → compose_question → END
                                          → (none)       → summarize → END
```
- `ingest_answer`: if `last_answer` is None (start) do nothing. If `kind == widget`, coerce `value` to the field type; if `kind == text`, call `llm.complete_structured(schema=ParsedFieldAnswer)` with the field's description and expected type to extract a value. Run the field validator; on failure set `error` and keep `current_field` (the next node then re-asks the same field). On success set `draft[field] = value`, append to `history`.
- `select_next_field`: first field in order not present in `draft` (12b only if `draft["medical_conditions"]` non-empty and not `["none"]`). Sets `current_field`.
- `compose_question`: `llm.complete_text` with the system prompt below and context `{field, field_description, draft_so_far, error}`; falls back to the field's static default question on `LLMError`. Attaches the static widget.
- `summarize`: sets `is_complete = True`, `message` = one warm sentence + "Here's what I've got — check it and hit Confirm."

Compiled with `AsyncPostgresSaver` checkpointer; thread id `onb_{user_id}`; `interrupt` is **not** used: each HTTP turn is one `graph.ainvoke` with `last_answer` set, and the graph ends after composing the question (state persists via checkpointer).

`ParsedFieldAnswer`:
```python
class ParsedFieldAnswer(BaseModel):
    value: str | float | list[str] | None      # None when the text does not answer the question
    confidence: float = Field(ge=0, le=1)
```

**System prompt — compose_question**
```
You are Larder's onboarding guide: a calm, friendly home cook helping someone set up their meal-planning profile.
Write ONE short sentence (max 25 words) asking for the field described in the context. Refer naturally to earlier answers when it helps
(e.g. use their name once you know it). Never ask for more than one thing. Never list options — the app shows a widget for that.
If `error` is present, start by gently acknowledging the problem in a few words, then re-ask.
Do not give medical advice. Do not use emojis. Output plain text only.
```

### 8.2 Planner agent

**Input and state (`agents/planner/state.py`)**

```python
class PlannerInput(BaseModel):
    job_id: UUID; plan_id: UUID; household_id: UUID; scope: Literal["family","single"]; member_id: UUID | None
    mode: Literal["week","today","slot"]; start_date: date; end_date: date
    target_date: date | None = None; target_slot_key: str | None = None; target_entry_id: UUID | None = None; swap_reason: str | None = None

class MemberCtx(BaseModel):
    id: UUID; display_name: str; diet_type: str; allergens: list[str]; dislikes: list[str]; likes: list[str]; cuisines: list[str]
    medical_conditions: list[dict]; medical_notes: str | None; goals: list[str]; cooking_skill: str | None; max_prep_minutes: int | None
    age: int | None; sex: str | None; activity_level: str | None

class PantryCtx(BaseModel): name: str; normalized_name: str; category: str; is_available: bool
class IngredientCtx(BaseModel): name: str; normalized_name: str; category: str; is_staple: bool; is_optional: bool
class MealCtx(BaseModel):
    id: UUID; name: str; description: str | None; cuisine: str | None; meal_types: list[str]; diet_tags: list[str]; allergens: list[str]
    prep_minutes: int | None; source: str; ingredients: list[IngredientCtx]
    feedback_up: int = 0; feedback_down: int = 0; cooked_count: int = 0; last_used_date: date | None = None

class FixedEntryCtx(BaseModel): date: date; slot_key: str; meal_name: str; meal_id: UUID

class PlanningContext(BaseModel):
    members: list[MemberCtx]; pantry: list[PantryCtx]; library: list[MealCtx]; slots: list[SlotDef]
    recent_meal_ids: list[UUID]                 # used in the 14 days before start_date, any scope
    fixed_entries: list[FixedEntryCtx]          # today/slot modes: entries that stay
    replacing: list[FixedEntryCtx]              # today/slot modes: entries being swapped out (named in the prompt)
    requested: list[tuple[date, str]]           # (date, slot_key) pairs to fill
    library_count_and_max_updated: str

class MealCandidate(BaseModel): meal: MealCtx; coverage: float; score: float; covered: list[str]; missing: list[IngredientCtx]

class NewMealDraft(BaseModel):
    name: str = Field(max_length=80); description: str = Field(max_length=240); cuisine: str; meal_types: list[str]
    diet_tags: list[str]; allergens: list[str]; prep_minutes: int = Field(ge=5, le=240)
    ingredients: list[IngredientDraft] = Field(min_length=2, max_length=20)
class IngredientDraft(BaseModel): name: str; category: PantryCategory; is_staple: bool = False; is_optional: bool = False
class VariationDraft(BaseModel): member_id: UUID; note: str = Field(max_length=120)
class EntryDraft(BaseModel):
    date: date; slot_key: str; existing_meal_id: UUID | None = None; new_meal: NewMealDraft | None = None
    reason: str = Field(max_length=160); variations: list[VariationDraft] = []
    @model_validator(mode="after")  # exactly one of existing_meal_id / new_meal
class PlanDraft(BaseModel): entries: list[EntryDraft]

class PlannerState(TypedDict):
    input: PlannerInput; context: PlanningContext | None; inputs_hash: str | None
    shortlist: list[MealCandidate]; draft: PlanDraft | None
    violations: list[str]; warnings: list[str]; attempts: int; used_fallback: bool; persisted: bool
```

**Graph**

```
START → load_context → shortlist → draft_plan → validate ─(no violations)→ persist → END
                                        ▲             │(violations, attempts < 2)
                                        └── repair ◄──┘
                                                      │(violations, attempts == 2)
                                                      └→ fallback_fill → persist → END
```

- `load_context` (`context.py`): builds `PlanningContext` from the DB (see §7.4 for what feeds the hash); `requested` = all (date, slot) in `[start,end]` for `week`; all slots of `target_date` for `today`; the single pair for `slot`. `fixed_entries` = existing entries not in `requested`. Stores `inputs_hash` on the job immediately.
- `shortlist` (`shortlist.py`): for each library meal, skip if any hard-constraint conflict (allergen intersection with any member, diet incompatibility, hard medical rule); compute `coverage`; `score = coverage*0.6 + feedback_norm*0.25 + recency*0.15` where `feedback_norm = (up - down)/(up+down+1)` mapped to 0..1 and `recency = 0` if used within 7 days, `0.5` if within 14, else `1`. Keep `coverage >= 0.5` or `source == user`; sort by score; top 40.
- `draft_plan` (`prompts.py` + `graph.py`): `llm.complete_structured(schema=PlanDraft, temperature=0.2)` with context JSON `{mode, requested, slots, members (constraints only), pantry (available names by category), shortlist (id, name, coverage, missing names, feedback), recent_meal_names, fixed_entries, swap_reason, soft_rules}`.
- `validate` (`validate.py`) returns `(violations, warnings)`:
  - **Hard**: every requested (date, slot) appears exactly once and nothing else; `existing_meal_id` must be in the shortlist or library; new meal allergens ∩ any member allergens = ∅; every member's diet compatible; hard medical rules; a meal id or normalised new-meal name may appear at most 2× in the plan window (counting fixed entries); `variations.member_id` must be a member; in `single` scope `variations` must be empty.
  - **Soft** (warnings only): ingredient tokens intersect a member's dislikes; `prep_minutes` > min member `max_prep_minutes`; coverage < 0.5 for more than 30% of entries; same cuisine 3 days in a row; `meal_types` does not include the slot key or `any`.
- `repair`: `llm.complete_structured(schema=PlanDraft)` with the previous draft, `violations` and `warnings`; `attempts += 1`.
- `fallback_fill` (`fallback.py`): for each violating entry (and any missing pair), pick the highest-scored shortlist candidate not already used twice; if the shortlist is exhausted, use the deterministic "Simple {slot} bowl" meal defined in §5.3 with `reason = "A simple fallback that fits everyone's constraints."`. Sets `used_fallback = True`. Validation is re-run once and must pass by construction (candidates are pre-filtered); if not, raise `PlannerError` → job failed.
- `persist` (`persist.py`), one transaction: for each `new_meal`, upsert into `meals` by `(household_id, normalized_name)` with `source = generated`, `enrichment_status = complete`, ingredients replaced; delete existing entries for `requested` pairs; insert entries with `covered_ingredients`/`missing_ingredients` computed against the pantry; insert variations; update job `attempts`, `used_fallback`, `model_name`, status `ready`.

**System prompt — draft_plan**
```
You are Larder's meal planner. You plan home-cooked meals that use what is already in the kitchen, so nothing goes to waste.
Return a plan as structured JSON matching the schema. Rules, in priority order:
1. SAFETY: never include a meal containing any listed allergen for any member. Respect every member's diet type and the medical rules given.
2. PANTRY FIRST: prefer meals from `shortlist` (they are already in this household's library and mostly covered by the pantry).
   When inventing a new meal, build it mainly from `pantry` items; keep missing ingredients to at most 2 non-staple items.
3. VARIETY: do not repeat a meal within the requested window more than twice; avoid `recent_meal_names`; vary cuisines across days.
4. FIT: match each slot's nature (breakfast = light/quick, snack = small). Keep prep within members' max_prep_minutes.
5. FAMILY: one meal per slot for everyone. Rotate members' `likes` fairly across the window. Use `variations` for small per-member tweaks
   (e.g. "no green chilli for Aarav") — never to give one member a different dish.
6. REASON: for every entry write one concrete sentence naming the pantry items it uses (e.g. "Uses the spinach and paneer you already have").
For mode=today or slot, fill ONLY the `requested` pairs and keep `fixed_entries` in mind for variety. `replacing` lists what is
currently in those slots: choose something different. For slot mode, honour `swap_reason`.
Use ingredient categories from: spices, grains, pulses, flours, dairy, vegetables, fruits, proteins, condiments, oils, snacks, beverages, frozen, other.
Mark salt, oil, water, sugar and everyday spices as is_staple=true.
```

**System prompt — repair** (appended to the above): `The previous draft violated these rules: {violations}. Also improve: {warnings}. Return a corrected full draft for the same requested pairs; change as little as possible.`

### 8.3 Meal enrichment (`agents/enrichment`)

```python
class MealEnrichment(BaseModel):
    description: str = Field(max_length=240); cuisine: str; meal_types: list[str]; diet_tags: list[str]; allergens: list[str]
    prep_minutes: int = Field(ge=5, le=240); ingredients: list[IngredientDraft] = Field(min_length=1, max_length=25)

async def enrich_meal(llm: LLM, *, name: str, description: str | None, ingredients: list[str] | None, instructions: str | None, slot_keys: list[str]) -> MealEnrichment
```
System prompt: `You are a culinary data assistant. Given a home-cooked dish, return its normalised ingredient list (one entry per ingredient, no quantities, mark staples and optional items), cuisine slug, suitable meal types from the given slot keys, diet tags from the allowed set, allergens from the allowed set, and realistic prep time in minutes. If the user supplied ingredients, keep them all and add only obvious omissions. Temperature 0.` Diet tags and allergens are validated against the vocabularies; unknown values are dropped.

### 8.4 Pantry categoriser (`agents/categorize`)

- `keyword_map.py`: `KEYWORDS: dict[str, PantryCategory]` with ~250 normalised names (Indian and general staples: `paneer→dairy, toor dal→pulses, basmati rice→grains, atta→flours, cumin→spices, …`) and `SUGGESTIONS: list[tuple[str, PantryCategory]]` (~60 items for the setup screen).
- `categorize(llm, names) -> dict[str, PantryCategory]`: exact map hit → done; else token hit (`"red onion"` → `onion`); remaining names in one `complete_structured(schema=CategoryAssignments)` call (`assignments: list[{name, category}]`); on `LLMError` → `other`.

---

## 9. Frontend

### 9.1 Shared package `@larder/design-tokens`

```ts
export const palette = {
  light: { bg: "#F7F4EE", surface: "#FFFFFF", surfaceAlt: "#F1ECE3", ink: "#1F1D1A", inkMuted: "#6B655C", line: "#E6E0D6",
           accent: "#B4532A", accentInk: "#FFFFFF", accentSoft: "#F4E3DA", success: "#3E7C4A", warning: "#B7791F", danger: "#B42318", focus: "#2F5D9F" },
  dark:  { bg: "#16140F", surface: "#1F1C16", surfaceAlt: "#26221B", ink: "#EFE9DF", inkMuted: "#A39B8E", line: "#2E2A22",
           accent: "#E07A4B", accentInk: "#16140F", accentSoft: "#3A251B", success: "#7FB98A", warning: "#D9A441", danger: "#E5735F", focus: "#8AB4F8" },
} as const;
export const type = { display: "Fraunces", body: "Instrument Sans", mono: "JetBrains Mono",
  scale: { xs: 12, sm: 14, md: 16, lg: 18, xl: 22, "2xl": 28, "3xl": 36 }, lineHeight: { tight: 1.15, normal: 1.5 } } as const;
export const space = [0, 4, 8, 12, 16, 24, 32, 48, 64] as const;   // index = step
export const radius = { sm: 4, md: 6, lg: 10 } as const;
export function toCssVariables(theme: "light" | "dark"): string  // ":root{--bg:#F7F4EE;…}" used by web globals.css
```

### 9.2 Visual rules (apply to both apps; reviewers check these)

1. One accent colour (terracotta). Everything else is paper, ink and lines. No gradients, no glassmorphism, no drop-shadow stacks; elevation is a 1px `line` border.
2. Headings in Fraunces (serif) at weights 500–600, left-aligned; body in Instrument Sans. Never centre-align long text.
3. Layout is lists and simple two-column sections, not grids of cards. A "card" is only used for a meal entry and is a bordered block with 6px radius.
4. Icons: Lucide, 20px, stroke 1.75, ink colour. No emoji as icons.
5. Empty states are a single sentence plus one action, in muted ink. No illustrations.
6. Motion: only opacity/transform ≤ 160 ms. Skeletons are flat `surfaceAlt` blocks.
7. Copy style: short, warm, specific ("Uses the spinach you have", not "Delicious healthy option!"). Sentence case everywhere.
8. Theme: follows system by default; a toggle in More/Profile persists `light | dark | system` in localStorage (web) / AsyncStorage (mobile).
9. Touch targets ≥ 44px on mobile; focus ring `focus` colour, 2px, visible on web.
10. Density: 16px page gutter on phones, 24px on tablet/desktop; max content width 880px on web.

### 9.3 Shared package `@larder/api-client`

```ts
// client.ts
export type GetToken = () => Promise<string | null>;
export function createApi(baseUrl: string, getToken: GetToken): Client<paths>   // openapi-fetch with auth middleware
export class ApiError extends Error { code: string; status: number; details?: unknown }
// hooks/*.ts (TanStack Query; each takes the api instance from ApiProvider context)
useMe(), useUpdateMe(), useOnboardingStart(), useOnboardingTurn(), useOnboardingComplete(),
useHousehold(), useUpdateHousehold(), useCreateInvite(), useJoinHousehold(), useRemoveMember(), useSetPreferredView(),
usePantry(), useAddPantryItems(), useUpdatePantryItem(), useDeletePantryItem(), usePantrySuggestions(),
useMeals(params), useMeal(id), useCreateMeal(), useUpdateMeal(), useDeleteMeal(), useEnrichMeal(), useFeedback(),
useCurrentPlan({scope, date}), useGeneratePlan(), useSwapEntry(), useJob(jobId, {pollMs: 2000, until: ready|failed}), useShoppingList(planId)
```
Query keys: `["me"]`, `["household"]`, `["pantry"]`, `["meals", params]`, `["plan", scope, date]`, `["job", id]`, `["shopping", planId]`. Mutations invalidate the obvious keys; `useJob` invalidates `["plan"]` when the job reaches `ready`.

`schema.d.ts` is generated by `pnpm gen` with the API running locally and is committed. Generated paths already include `/api/v1`, so `createApi` takes the API **origin** (a trailing `/api/v1` is tolerated and stripped). openapi-typescript v7 treats fields with defaults as required, so request bodies spell out defaulted fields.

### 9.4 Web app (`apps/web`)

Routes (App Router):

| Route | Screen | Notes |
|-------|--------|-------|
| `/sign-in`, `/sign-up` | Auth | Supabase email + password; on success → `/` |
| `/` | Router | `GET /me`: pending/in_progress → `/onboarding`; complete → `/today` |
| `/onboarding` | Onboarding chat | Transcript + `WidgetRenderer`; review card → Confirm → `/pantry/setup` |
| `/pantry/setup` | Pantry setup | Textarea bulk-add (comma/newline separated), suggestion chips, "Skip for now" → `/today` |
| `/today` | Today | Slot list for today: `PlanEntryCard`s, coverage line, "unused this week" line, swap and feedback actions, job progress banner |
| `/week` | Week | 7 columns on desktop / stacked days on mobile widths; "Regenerate week" |
| `/pantry` | Pantry | Category sections with inline add, availability toggle, rename, delete |
| `/meals`, `/meals/new`, `/meals/[id]` | Library | List with search and filters; create form (name, description, ingredients textarea, instructions); detail with enrichment status and edit |
| `/shopping` | Shopping | Grouped list with meal references; checkbox state is local only |
| `/household` | Household | Members, invite code (owner), join by code, preferred view toggle, slots editor, refresh schedule, timezone |
| `/profile` | Profile | Editable profile fields grouped: basics, diet, health (with "clear health data"), preferences; theme toggle |

Auth guard: `src/lib/supabase/middleware.ts` refreshes the session and redirects unauthenticated requests to `/sign-in` for all routes except auth pages; it is invoked from `src/proxy.ts` (Next.js 16's name for middleware). API calls happen from client components through `createApi(NEXT_PUBLIC_API_URL, () => supabase.auth.getSession().then(s => s.data.session?.access_token ?? null))`.

Key components (`src/components`): `ui/{Button,Input,Select,Chip,Toggle,Sheet,Banner,Skeleton,EmptyState}`, `onboarding/{Transcript,WidgetRenderer,ReviewCard}`, `plan/{PlanEntryCard,SlotHeader,CoverageLine,SwapSheet,FeedbackBar,JobBanner,ViewToggle}`, `pantry/{CategorySection,QuickAdd,BulkAdd,SuggestionChips}`, `meals/{MealList,MealForm,IngredientList}`, `household/{MemberList,InviteCode,JoinForm,SlotsEditor,ScheduleForm}`.

`PlanEntryCard` anatomy (top to bottom): slot label (small caps, muted) · meal name (display font, xl) · reason sentence · coverage row: "On hand: spinach, paneer · Missing: cream (optional)" with missing in warning colour · variations as "Aarav: no green chilli" lines · action row: thumbs up, thumbs down, "Cooked it", "Swap".

### 9.5 Mobile app (`apps/mobile`)

Expo Router file tree:

```
app/_layout.tsx                 providers: Supabase session, ApiProvider, QueryClient, Theme
app/(auth)/sign-in.tsx  sign-up.tsx
app/onboarding.tsx
app/pantry-setup.tsx
app/(tabs)/_layout.tsx          tabs: Today, Week, Pantry, Meals, More
app/(tabs)/today.tsx  week.tsx  pantry.tsx  meals/index.tsx  meals/new.tsx  meals/[id].tsx
app/(tabs)/more/index.tsx  shopping.tsx  household.tsx  profile.tsx
```
Session storage via `expo-secure-store` adapter; `AppState` listener calls `supabase.auth.startAutoRefresh()`. Fonts loaded with `expo-font` (Fraunces, Instrument Sans). The component set mirrors web names so the LLD screen specs apply to both.

### 9.6 Onboarding widget behaviour (both apps)

- The transcript shows assistant messages left-aligned in `surface` blocks and user answers right-aligned as plain text summaries ("172 cm").
- `WidgetRenderer` maps `type` → control; submit sends `{kind: "widget", value}`. A secondary "Type instead" link switches to a text input that sends `{kind: "text", text}`.
- While waiting for a turn: disable input, show a three-dot skeleton for ≤ 4 s, then a "Still thinking…" note.
- Review card lists all fields with an Edit link per group that jumps to `/profile`-style inline editing before Confirm; Confirm calls `/onboarding/complete` with `overrides`.

### 9.7 Plan job UX

After `generate`/`swap`, show `JobBanner` ("Planning your week from what's in the larder…") and poll `useJob`. On `ready`, invalidate the plan query and fade the banner. On `failed`, show "Couldn't finish planning. Your previous plan is unchanged." with a Retry button. Never block the rest of the screen.

---

## 10. Testing

### 10.1 API

- `tests/conftest.py`: sets `APP_ENV=test`, `AUTH_MODE=hs256`, `SUPABASE_JWT_SECRET=test-secret`, `LLM_PROVIDER=fake`, `DATABASE_URL=$TEST_DATABASE_URL` (default `postgresql+asyncpg://postgres:postgres@localhost:5433/larder_test`), runs `alembic upgrade head` once per session, truncates all tables between tests, provides `client` (httpx `AsyncClient` with `ASGITransport`), `auth_headers(user_id, email)` minting HS256 tokens, `fake_llm` (the app's provider instance), and factories `make_user_complete()` (profile + implicit household), `make_family(n)`, `add_pantry(household, names)`, `add_meal(household, ...)`.
- Unit (`tests/unit`): `test_normalize.py`, `test_coverage.py`, `test_hashing.py`, `test_shortlist.py`, `test_validate.py`, `test_diet_matrix.py`, `test_fallback.py`, `test_keyword_map.py`, `test_fields.py`, `test_shopping.py`, `test_unused.py`, `test_scheduler_due.py`.
- Agents (`tests/agents`): `test_onboarding_flow.py` (full 15-field conversation incl. one invalid answer and one text answer), `test_planner_week.py`, `test_planner_today.py`, `test_planner_slot.py`, `test_planner_repair.py` (fake scripted to violate an allergen once), `test_planner_fallback.py` (fake scripted to violate three times), `test_enrichment.py`, `test_categorize.py`.
- Integration (`tests/integration`): one file per router plus `test_auth.py` (missing/invalid/expired token, cross-household access returns 404) and `test_scheduler_tick.py` (weekly due/not due, daily unchanged hash skips, double tick idempotent, cleanup).
- Run: `uv run pytest -q`; coverage target 85% on `services`, `agents`, `routers`.

### 10.2 Web

- Vitest + RTL: `WidgetRenderer` (every widget type submits the right value shape), `PlanEntryCard` (renders reason, coverage, variations, feedback state), `BulkAdd` (parses "a, b\nc" into three names), theme toggle persists.
- Playwright (`e2e/`): runs `next dev` on port 3100 (never reusing a dev server on 3000) against `pnpm api` with `LLM_PROVIDER=fake`, `AUTH_MODE=jwks`, `SUPABASE_URL=http://127.0.0.1:54321` and `SUPABASE_ANON_KEY` set to the local anon key, with the local Supabase stack (`supabase start -x studio,imgproxy,mailpit,inbucket,logflare,vector,realtime,storage-api,edge-runtime,supavisor,pg-meta,postgrest`, config in `supabase/config.toml`). The local stack signs tokens with ES256, so JWKS mode is the one exercised. Spec `first-run.spec.ts`: sign up → answer all onboarding widgets → confirm → pantry setup adds 5 items → Today shows 4 entries with reasons → swap dinner → feedback up → Shopping shows missing items.

### 10.3 Mobile

jest-expo: `WidgetRenderer` and `PlanEntryCard` render and fire callbacks. No device e2e in v1.

### 10.4 CI (`.github/workflows/ci.yml`)

Jobs: `api` (services: postgres:16 on 5433; `uv sync`, `uv run ruff check`, `uv run pytest`), `js` (pnpm install, `pnpm typecheck`, `pnpm lint`, `pnpm test`). Playwright runs only on a manual dispatch to keep CI simple.

---

## 11. Deployment artefacts

**`apps/api/Dockerfile`**
```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/src"
CMD ["sh", "-c", "alembic upgrade head && uvicorn larder.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

**`render.yaml`**
```yaml
services:
  - type: web
    name: larder-api
    runtime: docker
    rootDir: apps/api
    plan: free
    healthCheckPath: /api/v1/health
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: GROQ_API_KEY
        sync: false
      - key: GROQ_MODEL
        value: openai/gpt-oss-120b
      - key: SCHEDULER_SECRET
        generateValue: true
      - key: CORS_ORIGINS
        sync: false
      - key: APP_ENV
        value: production
  - type: cron
    name: larder-scheduler
    runtime: docker
    rootDir: apps/api
    schedule: "*/15 * * * *"
    dockerCommand: sh -c 'curl -fsS -X POST "$API_URL/api/v1/internal/scheduler/tick" -H "X-Scheduler-Secret: $SCHEDULER_SECRET"'
    envVars:
      - key: API_URL
        sync: false
      - key: SCHEDULER_SECRET
        fromService:
          type: web
          name: larder-api
          envVarKey: SCHEDULER_SECRET
```

**Vercel**: project root `apps/web`, framework Next.js, install command `pnpm install --frozen-lockfile` at repo root (enable "Include files outside root directory"). Env vars as in HLD §9.

**Supabase**: enable Email provider; disable "Confirm email" for the POC; copy the *Session pooler* connection string into `DATABASE_URL` with `postgresql+asyncpg://` scheme; Auth → JWT keys → note whether the project uses asymmetric keys (default `AUTH_MODE=jwks` works) or a legacy secret (`AUTH_MODE=hs256` + `SUPABASE_JWT_SECRET`).

**`.env.example`** (root, copied into each app as needed):
```
# api
APP_ENV=local
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/larder
SUPABASE_URL=
SUPABASE_JWT_SECRET=
AUTH_MODE=jwks
LLM_PROVIDER=fake
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b
SCHEDULER_SECRET=dev-secret
CORS_ORIGINS=http://localhost:3000
# web
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8000
# mobile
EXPO_PUBLIC_SUPABASE_URL=
EXPO_PUBLIC_SUPABASE_ANON_KEY=
EXPO_PUBLIC_API_URL=http://localhost:8000
```

---

## 12. Glossary

| Term | Meaning |
|------|---------|
| Household | The group sharing one pantry; every user is in exactly one |
| Implicit household | Auto-created one-person household; replaced when the user joins another |
| Scope | Which profiles a plan honours: `family` (all members) or `single` (one member) |
| Slot | A named meal of the day (`breakfast`, `lunch`, …) configured per household |
| Coverage | Share of a meal's non-staple ingredients present in the pantry |
| Staple | Ingredient assumed always present (salt, oil, everyday spices); ignored for coverage and shopping |
| Inputs hash | SHA-256 of planner-relevant inputs; unchanged hash means the daily refresh is skipped |
| Refresh run | Idempotency record of a scheduler decision for a household and period |
| Job | A single planner execution (week, today or slot) with a status that clients poll |
