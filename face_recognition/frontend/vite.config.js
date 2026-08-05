import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Relative asset URLs so the built SPA works both standalone and behind
  // Home Assistant's Ingress reverse proxy, which serves it under a
  // per-installation path prefix (/api/hassio_ingress/<token>/) that isn't
  // known at build time.
  base: './',
  server: {
    port: 3080,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
