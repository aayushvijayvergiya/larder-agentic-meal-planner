import { defineConfig, devices } from "@playwright/test";

/** Runs against `next dev` on port 3100 (so a dev server on 3000 is never reused) with the API
 *  (LLM_PROVIDER=fake) and the local Supabase stack already running. */
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3100",
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: process.env.E2E_NO_SERVER
    ? undefined
    : {
        command: "pnpm dev --port 3100",
        url: "http://localhost:3100/sign-in",
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
