# Deployment guide

Target architecture: web on Vercel, API + cron on Render, database and auth on Supabase. See `docs/HLD.md` §9 and `docs/LLD.md` §11 for the design this follows.

## 1. Supabase (database + auth)

1. Create a project at [supabase.com](https://supabase.com).
2. **Authentication → Providers**: enable Email. For the POC, turn off "Confirm email" (Authentication → Settings) so sign-up works without an email server.
3. **Project Settings → Database → Connection string**: copy the **Session pooler** URI (not the direct connection — Render's network doesn't support IPv6, which the direct URI requires). Rewrite its scheme from `postgresql://` to `postgresql+asyncpg://`. This becomes `DATABASE_URL`.
4. **Project Settings → API**: copy the **Project URL** (`SUPABASE_URL`) and the **anon/publishable key** (`NEXT_PUBLIC_SUPABASE_ANON_KEY` / `EXPO_PUBLIC_SUPABASE_ANON_KEY`).
5. **Authentication → Sign in / providers → JWT Keys**: note whether the project uses asymmetric JWT signing (new projects default to this — leave `AUTH_MODE=jwks`, no extra secret needed) or a legacy shared HS256 secret (older projects — set `AUTH_MODE=hs256` and copy the JWT secret into `SUPABASE_JWT_SECRET`).

## 2. Render (API + scheduler)

1. Push the repo to GitHub (Render deploys from a GitHub connection).
2. In the Render dashboard: **New → Blueprint**, point it at the repo. Render reads `render.yaml` at the repo root and proposes the `larder-api` web service and `larder-scheduler` cron job.
3. Before the first deploy, set the env vars Render leaves blank (`sync: false` in `render.yaml`):
   - On **larder-api**: `DATABASE_URL`, `SUPABASE_URL`, `CORS_ORIGINS` (the Vercel URL once you have it, comma-separated if you add a custom domain later). Leave `GROQ_API_KEY` empty for now — the API falls back to `LLM_PROVIDER=fake` automatically.
   - On **larder-scheduler**: `API_URL` (the `larder-api` service's public `onrender.com` URL, e.g. `https://larder-api.onrender.com`). `SCHEDULER_SECRET` is wired automatically from the web service via `fromService`.
4. Deploy the blueprint. The API's Dockerfile runs `alembic upgrade head` on container start, so the schema is created on first boot — no separate migration step.
5. Confirm: `curl -s https://<larder-api>.onrender.com/api/v1/health` returns `{"status":"ok","database":"ok","llm_provider":"fake"}`.
6. When you have a Groq key, add `GROQ_API_KEY` to **larder-api** and trigger a manual redeploy (or restart) — `LLM_PROVIDER` auto-switches to `groq` when the key is present; no code change needed.

## 3. Vercel (web)

1. Import the GitHub repo as a new Vercel project.
2. **Project Settings → General → Root Directory**: `apps/web`. Under "Root Directory", enable **"Include files outside the root directory in the Build Step"** (the monorepo's `pnpm-lock.yaml` and shared packages live above `apps/web`).
3. Framework preset: Next.js (auto-detected). Install command: `pnpm install --frozen-lockfile`.
4. **Environment Variables**: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL` (the Render API's public URL from step 2.5).
5. Before the first production build, regenerate the API client against the deployed API so the web app's types match: `pnpm gen` with `NEXT_PUBLIC_API_URL` pointed at Render, then commit the regenerated `packages/api-client` output — Vercel builds from the committed schema rather than calling the API at build time.
6. Deploy. Once you have the Vercel URL, go back to Render and set `CORS_ORIGINS` on **larder-api** to that URL, then redeploy the API.

## 4. Mobile (Expo)

1. Development: `pnpm --filter mobile dev` and open in Expo Go, pointing `EXPO_PUBLIC_API_URL` at your local API or the deployed Render API.
2. Installable builds: `eas build --profile preview`, with `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY`, `EXPO_PUBLIC_API_URL` set as build-time env vars in `eas.json` (or as EAS project secrets so they aren't committed).

## 5. CI

`.github/workflows/ci.yml` runs on every push/PR: the `api` job (Postgres 16 service container, `uv sync`, `ruff check`, `pytest`) and the `js` job (`pnpm typecheck`, `pnpm lint`, `pnpm test`). Playwright e2e is intentionally not in CI — run it manually with `pnpm --filter web e2e` before a release.

## 6. Real-LLM smoke test

Once `GROQ_API_KEY` is set on Render: sign up, complete onboarding, and generate a week plan against the live deployment. Check the `plan_jobs` row for that plan has `model_name = 'openai/gpt-oss-120b'`, `attempts <= 2`, and `used_fallback = false`. Record the observed end-to-end latency here once measured:

| Date | Operation | Observed latency |
|------|-----------|-------------------|
| _pending_ | Week plan (populated pantry) | _pending_ |

## 7. Release tag

After final verification (Task 34 in `docs/IMPLEMENTATION_PLAN.md`) passes, tag the release: `git tag v1.0.0-poc && git push origin v1.0.0-poc`.
