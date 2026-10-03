import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // MapLibre spawns a Web Worker to do tile parsing and style work. Vite's
  // dependency pre-bundling rewrites maplibre-gl's import.meta.url to point at
  // a single optimized chunk, but never emits the companion
  // `maplibre-gl-worker.mjs` alongside it, so the worker request 404s. MapLibre
  // then renders a correctly sized but permanently blank canvas, with no error
  // on screen. Excluding the package from pre-bundling keeps the worker
  // resolvable; `worker.format` keeps the worker an ES module under Vite.
  optimizeDeps: {
    exclude: ["maplibre-gl"],
  },
  worker: {
    format: "es",
  },
  server: {
    // Without this Vite binds to whatever `localhost` resolves to, which on
    // Windows is often ::1 alone. The dev server then refuses connections on
    // 127.0.0.1 even though it is running, so a browser pointed at the IPv4
    // address shows a connection error with no obvious cause. Pinning the
    // loopback keeps the server off the network and reachable either way.
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
