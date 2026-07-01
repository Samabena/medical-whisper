import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En dev, on relaie l'API et le WebSocket vers le backend FastAPI (port 8000).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": { target: "http://localhost:8000", changeOrigin: true, ws: true },
      "/admin/api": { target: "http://localhost:8000", changeOrigin: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
