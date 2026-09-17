import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** Configure the React compiler, tests, and development API proxy. */
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    exclude: ["e2e/**", "node_modules/**", "dist/**"]
  }
});
