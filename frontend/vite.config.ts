import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/media": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Stable vendor chunks: cached once, never re-downloaded.
        manualChunks(id) {
          if (/[\\/]node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(id)) {
            return "react";
          }
          if (/[\\/]node_modules[\\/]react-router/.test(id)) {
            return "router";
          }
        },
      },
    },
  },
});
