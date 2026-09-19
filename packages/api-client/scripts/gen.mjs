#!/usr/bin/env node
// Regenerates src/schema.d.ts from a running API. Usage: API_URL=http://localhost:8000 pnpm gen
// A plain Node script (not a shell script) so it runs the same under PowerShell, cmd, bash and CI.
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const apiUrl = process.env.API_URL ?? "http://localhost:8000";

const result = spawnSync(
  "npx",
  ["openapi-typescript@7", `${apiUrl}/openapi.json`, "-o", "src/schema.d.ts"],
  { cwd: packageRoot, stdio: "inherit", shell: true },
);

process.exit(result.status ?? 1);
