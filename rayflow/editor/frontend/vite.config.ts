import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/editor/',
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/editor/nodes': 'http://127.0.0.1:8000',
      '/editor/flows': 'http://127.0.0.1:8000',
      '/editor/validate': 'http://127.0.0.1:8000',
      '/editor/type-check': 'http://127.0.0.1:8000',
    },
  },
})
