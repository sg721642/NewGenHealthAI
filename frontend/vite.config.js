import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({mode}) => ({
  plugins: [react()],
  build: {
    // STANDALONE_BUILD=1 → output to dist/ (standalone frontend container)
    // Default → output to backend static dir for Docker unified build
    outDir: mode === 'standalone' ? 'dist' : '../backend/app/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    environmentOptions: {
      happyDOM: {
        // Enable localStorage support
        url: 'http://localhost',
      },
    },
    setupFiles: './src/setupTests.js',
    css: false,
  },
}))
