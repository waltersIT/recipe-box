import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backend = 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The Django API and uploaded media are served through the dev server, so
    // the browser only ever talks to one origin (no CORS setup needed).
    proxy: {
      '/api': backend,
      '/media': backend,
    },
  },
})
