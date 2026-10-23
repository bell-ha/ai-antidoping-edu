import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8100" } }, // npm run dev(5173) → 서버(8100). 8000은 다른 프로젝트가 씀
});
