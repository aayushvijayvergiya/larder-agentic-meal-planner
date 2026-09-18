#!/usr/bin/env sh
# Regenerates src/schema.d.ts from a running API. Usage: API_URL=http://localhost:8000 pnpm gen
set -e
cd "$(dirname "$0")/.."
npx openapi-typescript@7 "${API_URL:-http://localhost:8000}/openapi.json" -o src/schema.d.ts
