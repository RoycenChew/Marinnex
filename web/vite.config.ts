import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import svgr from 'vite-plugin-svgr'

const webRoot = fileURLToPath(new URL('.', import.meta.url))
const fdipRoot = fileURLToPath(new URL('..', import.meta.url))

export default defineConfig({
  // svgr so the logo can be inlined as a component and inherit currentColor.
  // An <img src="*.svg"> is an isolated document and renders currentColor as
  // black, which is why the mark could not follow the theme before.
  plugins: [react(), tailwindcss(), svgr()],
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
