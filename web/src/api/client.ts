import createClient from 'openapi-fetch'
import type { paths } from './v1'

/**
 * The API origin, **without** a version segment.
 *
 * The generated path keys in `v1.d.ts` already start with `/v1/` (they are taken
 * verbatim from `openapi.json`), so a base URL ending in `/v1` produced
 * `/v1/v1/auth/me` on every single call. The version lives in the paths; the base
 * is the origin only.
 */
const API_ORIGIN = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export const apiClient = createClient<paths>({
  baseUrl: API_ORIGIN,
  // The session is an httpOnly cookie, so every request has to carry it.
  credentials: 'include',
})

apiClient.use({
  onRequest({ request }) {
    // Never set Content-Type on a multipart upload: the browser has to supply it
    // with the boundary, and overriding it makes the backend reject the body.
    if (!(request.headers.get('Content-Type') ?? '').startsWith('multipart/')) {
      request.headers.set(
        'Content-Type',
        request.headers.get('Content-Type') || 'application/json',
      )
    }
    return request
  },
})

export { API_ORIGIN }
