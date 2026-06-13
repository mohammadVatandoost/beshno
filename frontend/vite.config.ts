import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development the frontend proxies /api to the FastAPI backend so the
// browser talks to a single origin (no CORS juggling). In production, set
// VITE_API_BASE to the backend URL at build time.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
