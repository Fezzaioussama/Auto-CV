import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Vite builds the SPA into ../static/spa so Flask serves it from /static/spa/.
// In dev, the Vite server runs at :5173 and proxies /api + /auth + /login etc.
// to Flask at :5000 — Flask still owns those endpoints in production.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  base: "/static/spa/",
  build: {
    outDir: path.resolve(__dirname, "../static/spa"),
    emptyOutDir: true,
    assetsDir: "assets",
    sourcemap: false,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:5000",
      "/login": "http://localhost:5000",
      "/logout": "http://localhost:5000",
      "/register": "http://localhost:5000",
      "/forgot-password": "http://localhost:5000",
      "/reset-password": "http://localhost:5000",
      "/resend-verification": "http://localhost:5000",
      "/verify-email": "http://localhost:5000",
    },
  },
});
