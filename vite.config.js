import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'https://d2vdbk8mo3xmgf.cloudfront.net',
        changeOrigin: true,
        secure: true,
      }
    }
  }
})