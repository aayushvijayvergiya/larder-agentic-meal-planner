# Larder

A pantry-first, zero-waste meal planner for individuals and families. The planner starts from what is in your kitchen, plans to use it up, explains every pick, and only then suggests a short top-up shopping list. Families get one shared menu that honours everyone's constraints with per-member notes.

## Layout

- `apps/api` — FastAPI + LangGraph backend (Python 3.12, uv)
- `apps/web` — Next.js web app
- `apps/mobile` — Expo mobile app
- `packages/api-client` — generated OpenAPI client and TanStack Query hooks
- `packages/design-tokens` — colours, type and spacing shared by web and mobile
- `docs/` — `HLD.md`, `LLD.md`, `IMPLEMENTATION_PLAN.md`, `Requirements.md`

## Run locally

1. Start Postgres: `docker run -d --name larder-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=larder -p 5432:5432 postgres:16`
2. Copy `.env.example` to `apps/api/.env` and adjust `DATABASE_URL` if needed. With no `GROQ_API_KEY` the API uses a deterministic fake LLM.
3. API: `pnpm api` (runs migrations via `uv run alembic upgrade head` first if the DB is empty).
4. API tests: start a test DB on port 5433 (`-e POSTGRES_DB=larder_test`) and run `pnpm api:test`.
5. Web and mobile: `pnpm install` then `pnpm dev`.

See `docs/HLD.md` for the architecture, `docs/LLD.md` for every contract, and `docs/IMPLEMENTATION_PLAN.md` for the build order.
