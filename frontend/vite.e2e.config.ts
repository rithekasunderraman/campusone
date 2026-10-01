import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server used ONLY by the browser end-to-end tests. It is hard-wired to the
// throwaway test backend on :8001 so a test run can never reach the real
// backend on :8000 (and therefore never the real database).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8001", changeOrigin: true },
    },
  },
});
