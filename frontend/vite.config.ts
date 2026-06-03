import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Forward API calls to the FastAPI backend when running locally
      '/upload': 'http://localhost:8000',
      '/ask': 'http://localhost:8000',
      '/analyze': 'http://localhost:8000',
      '/compare': 'http://localhost:8000',
      '/metrics': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
  build: {
    // Default dist/ for Docker; local `make frontend` copies to backend/static
    outDir: 'dist',
    emptyOutDir: true,
  },
})
