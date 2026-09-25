import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // The full plotly.js bundle alone is ~5 MB (1.5 MB gzip); raise the limit
    // so real regressions still warn. Internal tool — bundle size accepted.
    chunkSizeWarningLimit: 6000,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/logo.png': 'http://localhost:8000',
    },
  },
})
