import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const webRoot = fileURLToPath(new URL('.', import.meta.url))
const fdipRoot = fileURLToPath(new URL('..', import.meta.url))

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    fs: {
      // The MSW fixtures are fdip/samples/examples.json, which sits outside the
      // Vite root. They are captured from a real mock-mode backend run and are
      // the source of truth for VITE_USE_MOCKS, so the dev server has to be
      // allowed to read one level up.
      allow: [webRoot, fdipRoot],
    },
  },
})
