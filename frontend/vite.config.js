import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api -> backend. Compartido por dev (server) y preview (preview),
// para que la build de producción también hable con la API sin CORS.
const proxy = {
  "/api": {
    target: "http://127.0.0.1:8010",
    changeOrigin: true,
    configure: (proxy, _options) => {
      proxy.on("proxyReq", (proxyReq, req, _res) => {
        // Reenviar Authorization header
        const auth = req.headers.authorization;
        if (auth) {
          proxyReq.setHeader("Authorization", auth);
        }
      });
    },
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    proxy,
  },
  preview: {
    port: 4173,
    proxy,
  },
});
