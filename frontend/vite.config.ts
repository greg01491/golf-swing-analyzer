import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // forward API calls to the Python backend (config.yaml api.host/port)
    proxy: {
      '/api': 'http://127.0.0.1:8765',
    },
  },
})
