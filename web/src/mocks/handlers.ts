import { http, HttpResponse } from 'msw';
// Three levels up, not two: this file is web/src/mocks/, so `../../` is web/.
// The captured responses live in fdip/samples/ beside the backend that produced
// them, which is also why vite.config.ts has to allow serving from outside the
// web/ root.
import examples from '../../../samples/examples.json';
import { buildAnalysis, buildSchemaList, buildTemplate, pageSvg } from './fixtures';

/** One captured response, keyed as `"<METHOD> /v1/<path>"`. */
type Example = { status: number; body: unknown };

// A cast is needed because the JSON is a flat map of route strings whose values
// are deliberately heterogeneous -- each one mirrors a different endpoint's
// response shape. Typing it per-route would duplicate the OpenAPI types that
// already describe them.
const captured = examples as unknown as Record<string, Example | undefined>;

/** The captured body for a key, or undefined. */
const captured_body = (key: string) => captured[key]?.body as Record<string, unknown> | undefined;

const getResponse = (key: string) => {
  const example = captured[key];
  if (!example) {
    // Loud rather than silent: a missing fixture should look like a missing
    // fixture, not like an empty screen.
    return HttpResponse.json(
      { code: 'mock_not_found', detail: `no captured response for "${key}"` },
      { status: 404 },
    );
  }
  return HttpResponse.json(example.body, { status: example.status });
};
export const handlers = [
  http.get('*/v1/auth/me', () => getResponse('GET /v1/auth/me')),
  http.post('*/v1/auth/login', () => HttpResponse.json({}, { status: 200 })),
  http.post('*/v1/auth/logout', () => HttpResponse.json({}, { status: 204 })),
  // Captured with three of its fields; the builder needs all of them.
  http.get('*/v1/templates', () => HttpResponse.json(buildTemplate())),
  http.post('*/v1/documents', () => getResponse('POST /v1/documents')),
  // `?empty=1` on the page URL returns an empty list, so the first-run welcome
  // and the empty states can be exercised in mock mode without deleting the
  // fixtures every other screen depends on.
  http.get('*/v1/documents', () =>
    new URLSearchParams(window.location.search).get('empty') === '1'
      ? HttpResponse.json({ items: [], total: 0 })
      : getResponse('GET /v1/documents'),
  ),
  
  // Note: for document processing, we need to return 'processing' status first, then 'completed' after some time if we want to simulate. 
  // Let's just return completed for now, or match on id.
  http.get('*/v1/documents/:id', ({ params }) => {
    if (params.id === 'doc_1m4an4f05hm4wn0vd') {
       return getResponse('GET /v1/documents/{id}');
    }
    return getResponse('GET /v1/documents/{id} (404, RFC 9457 error)');
  }),
  // The captured analysis body was trimmed to three fields when it was captured,
  // which would leave the review screen with nothing to review. `fixtures.ts`
  // rebuilds a full one from the same invoice. See its header.
  http.get('*/v1/documents/:id/analysis', ({ params }) => {
    const captured = captured_body('GET /v1/documents/{id}/analysis');
    if (String(params.id).includes('scan')) {
      return HttpResponse.json(
        buildAnalysis({
          status: 'needs_review',
          reasons: ['scanned_document_review'],
        }),
      );
    }
    return HttpResponse.json(buildAnalysis(captured ?? {}));
  }),

  // Binary, so it was never captured. The SVG is laid out at the same
  // coordinates as the mocked evidence boxes.
  http.get('*/v1/documents/:id/pages/:page/image', () =>
    // A plain HttpResponse, not HttpResponse.text(): the helper forces
    // `text/plain`, which the browser refuses to decode as an image.
    new HttpResponse(pageSvg(), {
      headers: { 'Content-Type': 'image/svg+xml', 'X-Page-Dpi': '150' },
    }),
  ),
  http.get('*/v1/documents/:id/extractions', () =>
    HttpResponse.json([buildAnalysis({})]),
  ),
  
  http.post('*/v1/extractions/:id/corrections', () => getResponse('POST /v1/extractions/{id}/corrections')),
  http.post('*/v1/extractions/:id/decision', () => getResponse('POST /v1/extractions/{id}/decision')),
  
  http.post('*/v1/schemas', () => getResponse('POST /v1/schemas')),
  http.get('*/v1/schemas', () => HttpResponse.json(buildSchemaList())),
  http.get('*/v1/schemas/:id', () => getResponse('GET /v1/schemas/{id}')),
  
  http.post('*/v1/schemas/:id/versions/:v/test-runs', () => getResponse('POST /v1/schemas/{id}/versions/{v}/test-runs')),
  http.get('*/v1/test-runs/:id', () => {
     // Return the body of the test run creation directly
     const res = (examples as any)['POST /v1/schemas/{id}/versions/{v}/test-runs'];
     return HttpResponse.json(res.body, { status: 200 });
  }),
  http.get('*/v1/schemas/:id/versions/:v/contract', () => getResponse('GET /v1/schemas/{id}/versions/{v}/contract')),
  
  http.post('*/v1/api-keys', () => getResponse('POST /v1/api-keys')),
  http.get('*/v1/api-keys', () => getResponse('GET /v1/api-keys')),
  
  http.post('*/v1/exports', () => getResponse('POST /v1/exports')),
  http.get('*/v1/usage', () => getResponse('GET /v1/usage')),
];
