import { defineConfig } from "@playwright/test";

/**
 * Browser end-to-end tests.
 *
 * Local (default): starts its own backend on :8001 against a throwaway copy of
 * the database and its own Vite server on :5174 — the live database and the
 * normal dev servers are not touched.
 *
 * Deployed: set E2E_BASE_URL=https://your-frontend-host to run the same flow
 * against a live deployment (no local servers are started).
 */
const deployed = process.env.E2E_BASE_URL;
const python = process.platform === "win32" ? "..\\backend\\venv\\Scripts\\python.exe" : "../backend/venv/bin/python";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: deployed || "http://localhost:5174",
    channel: process.env.E2E_CHANNEL || "msedge",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: deployed
    ? undefined
    : [
        {
          command: `${python} -m scripts.e2e_server`,
          cwd: "../backend",
          url: "http://127.0.0.1:8001/api/health",
          timeout: 300_000,
          reuseExistingServer: false,
        },
        {
          command: "npx vite --config vite.e2e.config.ts",
          url: "http://localhost:5174",
          timeout: 120_000,
          reuseExistingServer: false,
        },
      ],
});
