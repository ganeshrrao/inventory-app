import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // In Docker, VITE_BACKEND_HOST is set to http://backend:8000 by
      // docker-compose so Vite proxies to the backend container, not localhost.
      // Locally (npm run dev without Docker) the env var is unset so it falls
      // back to localhost:8000 — no change to your local workflow.
      '/api': {
        target: process.env.VITE_BACKEND_HOST || 'http://localhost:8000',
        changeOrigin: true,
      },
    }
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
  },
})
