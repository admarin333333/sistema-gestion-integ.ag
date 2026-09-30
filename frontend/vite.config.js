import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    // Proxy para evitar CORS: /api -> http://127.0.0.1:8010
    proxy: {
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
    },
  },
});
