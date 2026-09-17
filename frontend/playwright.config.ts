import { defineConfig } from "@playwright/test";

/** Configure serial live fullstack journeys, including production-auth rejection coverage. */
export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  workers: 1,
  fullyParallel: false,
  use: {
    baseURL: "http://127.0.0.1:5173",
    headless: true,
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {}
  },
  webServer: [
    {
      command: "bash -lc \"mongosh --quiet --eval \\\"const db = db.getSiblingDB('eqip_e2e'); db.dropDatabase(); db.demands.insertOne({ demand_id: 'DEM-READINESS-01', owner_actor_id: 'e2e-user', state: 'submitted', version: 0, resolution_note: null, history: [], updated_at: new Date() });\\\" && cd ../backend && MONGODB_URI=mongodb://127.0.0.1:27017 MONGODB_DB=eqip_e2e AUTH_MODE=development DEVELOPMENT_USER_ID=e2e-user CORS_ORIGINS=http://127.0.0.1:5173 \\\"$HOME/venvs/eqip/bin/python\\\" -m uvicorn app.main:app --host 127.0.0.1 --port 8000\"",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: true
    },
    {
      command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true
    },
    {
      command: "bash -lc 'cd ../backend && MONGODB_URI=mongodb://127.0.0.1:27017 MONGODB_DB=eqip_e2e AUTH_MODE=production CORS_ORIGINS=http://127.0.0.1:5174 \"$HOME/venvs/eqip/bin/python\" -m uvicorn app.main:app --host 127.0.0.1 --port 8001'",
      url: "http://127.0.0.1:8001/api/health",
      reuseExistingServer: true
    },
    {
      command: "bash -lc 'VITE_API_URL=http://127.0.0.1:8001 node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174'",
      url: "http://127.0.0.1:5174",
      reuseExistingServer: true
    }
  ]
});