/// <reference types="vitest/config" />
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  // The router plugin must come before react(): it generates src/routeTree.gen.ts from src/routes/.
  plugins: [tanstackRouter({ target: 'react', autoCodeSplitting: true }), react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  // Unit tests live next to the code in src/; e2e/ belongs to Playwright.
  test: { include: ['src/**/*.test.ts'] },
  server: {
    // In development the API runs separately (oim-shop serve); in production both share one origin.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
