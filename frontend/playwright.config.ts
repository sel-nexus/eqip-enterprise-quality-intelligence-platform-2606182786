import { defineConfig } from "@playwright/test";

/** Configure the live fullstack browser journey. */
export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  use: {
    baseURL: "http://127.0.0.1:5173",
    headless: true,
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {}
  },
  webServer: [
    {
      command: "bash -lc 'cd ../backend && MONGODB_URI=mongodb://127.0.0.1:27017 MONGODB_DB=eqip_e2e AUTH_MODE=development DEVELOPMENT_USER_ID=e2e-user CORS_ORIGINS=http://127.0.0.1:5173 \"$HOME/venvs/eqip/bin/python\" -m uvicorn app.main:app --host 127.0.0.1 --port 8000'",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: true
    },
    {
      command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true
    }
  ]
});
