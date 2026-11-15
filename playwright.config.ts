import { defineConfig } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// The end-to-end tests run against their own backend and a freshly seeded
// database, so they never touch the queue that `npm run dev` serves.
const backend = "http://127.0.0.1:8100";

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  use: { baseURL: "http://localhost:5174" },
  webServer: [
    {
      command:
        "uv run -m backend.seed && uv run -m uvicorn backend.main:app --port 8100",
      url: `${backend}/api/health`,
      reuseExistingServer: false,
      env: { UNDERCOVER_DB: join(tmpdir(), "undercover-e2e.db") },
    },
    {
      command: "npx vite dashboard --port 5174 --strictPort",
      url: "http://localhost:5174",
      reuseExistingServer: false,
      env: { BACKEND_URL: backend },
    },
  ],
});
