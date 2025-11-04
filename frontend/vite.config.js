import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// ✅ This fixes invalid hook calls by forcing one React copy
// ✅ Also prevents Vite from importing backend files accidentally
export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ['react', 'react-dom'], // ensure single React instance
  },
  server: {
    fs: {
      strict: true, // disallow imports from outside frontend folder
    },
  },
})