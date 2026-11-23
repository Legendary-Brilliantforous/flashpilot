import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The site is published as static output. `base: './'` keeps every asset
// reference relative, so the same build works under a GitHub Pages project
// path, a custom domain, or a plain file server without a rebuild.
export default defineConfig({
  base: './',
  plugins: [react()],
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
})
