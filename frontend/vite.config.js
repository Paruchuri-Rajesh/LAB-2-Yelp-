import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite dev proxy: point `/api` and `/uploads` at the docker-compose
// frontend container (nginx on :8080) so Redux thunks and axios calls
// hit the correct per-domain API service. Override with the
// `VITE_PROXY_TARGET` env var when running services directly on the host.
const target = process.env.VITE_PROXY_TARGET || 'http://localhost:8080'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': target,
      '/uploads': target,
    },
  },
})
