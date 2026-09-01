import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  // Packaged Electron loads dist/index.html via file://, so assets must be
  // relative to that file rather than rooted at /assets.
  base: './',
  plugins: [react()],
  server: {
    // forward API calls to the Python backend (config.yaml api.host/port)
    proxy: {
      '/api': 'http://127.0.0.1:8765',
    },
  },
})
