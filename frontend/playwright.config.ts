import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";
process.env.PLAYWRIGHT_BROWSERS_PATH ??= resolve(".playwright");
export default defineConfig({
  testDir: "./tests",
  timeout: 60000,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5174",
    headless: true,
    screenshot: "only-on-failure",
  },
  reporter: "list",
  webServer: [
    {
      command:
        "..\\backend\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8001",
      url: "http://127.0.0.1:8001/api/health",
      reuseExistingServer: false,
      env: {
        PROTOTYPE_DB_PATH: resolve(
          "../data/runtime/e2e",
          `test-${Date.now()}.db`,
        ),
        LLM_PROVIDER: "unconfigured",
        RAG_RETRIEVAL_MODE: "lexical",
      },
    },
    {
      command: "npm run dev -- --port 5174",
      url: "http://127.0.0.1:5174",
      reuseExistingServer: false,
      env: { API_TARGET: "http://127.0.0.1:8001" },
    },
  ],
});
