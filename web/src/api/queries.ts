import { apiClient, API_ORIGIN } from './client'
import type {
  ApiKey,
  DocumentDetail,
  DocumentList,
  Extraction,
  SchemaSummary,
  Template,
  TestRun,
  Usage,
} from './types'

/**
 * Typed wrappers over the generated client.
 *
 * Two gaps in `openapi.json` are absorbed here rather than at every call site,
 * and both are logged in `web/BACKEND_REQUESTS.md`:
 *
 * 1. **`?project_id=` is undeclared.** `API_CONTRACT_FOR_UI.md` says every UI
 *    route accepts it, and the backend reads it, but it is pulled off the raw
 *    request inside a FastAPI dependency so it never reaches the schema. The
 *    generated types therefore reject it.
 * 2. **Response bodies are `{[key: string]: unknown}`**, because the handlers
 *    return bare dicts with no response model.
 *
 * The casts below are the whole of the workaround. They are confined to this
 * file so that every screen above it is honestly typed, and so that deleting
 * them when the backend is annotated is a single change.
 */

/** The undeclared-but-accepted query parameters, in one place. */
type ExtraQuery = Record<string, string | number | undefined>

function query(params: ExtraQuery) {
  const clean: ExtraQuery = {}
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') clean[key] = value
  }
  // `as never` targets openapi-fetch's `query?: never` on routes that declare no
  // parameters at all. See gap 1 above.
  return clean as never
}

function unwrap<T>(data: unknown, error: unknown): T {
  if (error) throw error
  return data as T
}

export async function listDocuments(options: {
  projectId: string | null
  status?: string
  limit?: number
  cursor?: string
}): Promise<DocumentList> {
  const { data, error } = await apiClient.GET('/v1/documents', {
    params: {
      query: query({
        project_id: options.projectId ?? undefined,
        status: options.status,
        limit: options.limit ?? 100,
        cursor: options.cursor,
      }),
    },
  })
  return unwrap<DocumentList>(data, error)
}

export async function getDocument(
  id: string,
  projectId: string | null,
): Promise<DocumentDetail> {
  const { data, error } = await apiClient.GET('/v1/documents/{document_id}', {
    params: {
      path: { document_id: id },
      query: query({ project_id: projectId ?? undefined }),
    },
  })
  return unwrap<DocumentDetail>(data, error)
}

export async function deleteDocument(
  id: string,
  projectId: string | null,
): Promise<void> {
  const { error } = await apiClient.DELETE('/v1/documents/{document_id}', {
    params: {
      path: { document_id: id },
      query: query({ project_id: projectId ?? undefined }),
    },
  })
  if (error) throw error
}

export async function getAnalysis(
  id: string,
  projectId: string | null,
): Promise<Extraction> {
  const { data, error } = await apiClient.GET(
    '/v1/documents/{document_id}/analysis',
    {
      params: {
        path: { document_id: id },
        query: query({ project_id: projectId ?? undefined }),
      },
    },
  )
  return unwrap<Extraction>(data, error)
}

export async function listExtractions(
  id: string,
  projectId: string | null,
): Promise<Extraction[]> {
  const { data, error } = await apiClient.GET(
    '/v1/documents/{document_id}/extractions',
    {
      params: {
        path: { document_id: id },
        query: query({ project_id: projectId ?? undefined }),
      },
    },
  )
  return unwrap<Extraction[]>(data, error)
}

export async function correctExtraction(
  extractionId: string,
  changes: { path: string; value: unknown }[],
  reason: string | undefined,
  projectId: string | null,
): Promise<Extraction> {
  const { data, error } = await apiClient.POST(
    '/v1/extractions/{extraction_id}/corrections',
    {
      params: {
        path: { extraction_id: extractionId },
        query: query({ project_id: projectId ?? undefined }),
      },
      body: { changes, reason },
    },
  )
  return unwrap<Extraction>(data, error)
}

export async function decideExtraction(
  extractionId: string,
  action: 'approve' | 'reject',
  reason: string | undefined,
  projectId: string | null,
): Promise<{ extraction_id: string; status: string }> {
  const { data, error } = await apiClient.POST(
    '/v1/extractions/{extraction_id}/decision',
    {
      params: {
        path: { extraction_id: extractionId },
        query: query({ project_id: projectId ?? undefined }),
      },
      body: { action, reason },
    },
  )
  return unwrap<{ extraction_id: string; status: string }>(data, error)
}

export async function listTemplates(projectId: string | null): Promise<Template[]> {
  const { data, error } = await apiClient.GET('/v1/templates', {
    params: { query: query({ project_id: projectId ?? undefined }) },
  })
  return unwrap<Template[]>(data, error)
}

export async function listSchemas(projectId: string | null): Promise<SchemaSummary[]> {
  const { data, error } = await apiClient.GET('/v1/schemas', {
    params: { query: query({ project_id: projectId ?? undefined }) },
  })
  return unwrap<SchemaSummary[]>(data, error)
}

export async function getSchema(
  id: string,
  projectId: string | null,
): Promise<SchemaSummary> {
  const { data, error } = await apiClient.GET('/v1/schemas/{schema_id}', {
    params: {
      path: { schema_id: id },
      query: query({ project_id: projectId ?? undefined }),
    },
  })
  return unwrap<SchemaSummary>(data, error)
}

export async function createSchema(
  body: {
    template_id: string
    name: string
    fields: string[]
    locale_hints: { date_order: string }
  },
  projectId: string | null,
): Promise<{ schema_id: string; version: number }> {
  const { data, error } = await apiClient.POST('/v1/schemas', {
    params: { query: query({ project_id: projectId ?? undefined }) },
    body,
  })
  return unwrap<{ schema_id: string; version: number }>(data, error)
}

export async function addSchemaVersion(
  schemaId: string,
  body: { fields: string[]; locale_hints: { date_order: string } },
  projectId: string | null,
): Promise<{ schema_id: string; version: number }> {
  const { data, error } = await apiClient.POST('/v1/schemas/{schema_id}/versions', {
    params: {
      path: { schema_id: schemaId },
      query: query({ project_id: projectId ?? undefined }),
    },
    body,
  })
  return unwrap<{ schema_id: string; version: number }>(data, error)
}

export async function getContract(
  schemaId: string,
  version: number,
  projectId: string | null,
): Promise<Record<string, unknown>> {
  const { data, error } = await apiClient.GET(
    '/v1/schemas/{schema_id}/versions/{version}/contract',
    {
      params: {
        path: { schema_id: schemaId, version },
        query: query({ project_id: projectId ?? undefined }),
      },
    },
  )
  return unwrap<Record<string, unknown>>(data, error)
}

export async function createTestRun(
  schemaId: string,
  version: number,
  documentIds: string[],
  projectId: string | null,
): Promise<TestRun> {
  const { data, error } = await apiClient.POST(
    '/v1/schemas/{schema_id}/versions/{version}/test-runs',
    {
      params: {
        path: { schema_id: schemaId, version },
        query: query({ project_id: projectId ?? undefined }),
      },
      body: { document_ids: documentIds },
    },
  )
  return unwrap<TestRun>(data, error)
}

export async function getTestRun(
  runId: string,
  projectId: string | null,
): Promise<TestRun> {
  const { data, error } = await apiClient.GET('/v1/test-runs/{run_id}', {
    params: {
      path: { run_id: runId },
      query: query({ project_id: projectId ?? undefined }),
    },
  })
  return unwrap<TestRun>(data, error)
}

export async function listApiKeys(projectId: string | null): Promise<ApiKey[]> {
  const { data, error } = await apiClient.GET('/v1/api-keys', {
    params: { query: query({ project_id: projectId ?? undefined }) },
  })
  return unwrap<ApiKey[]>(data, error)
}

export async function createApiKey(
  body: {
    name: string
    mode: 'live' | 'test'
    schema_versions: { schema_id: string; version: number }[]
    expires_at?: string | null
  },
  projectId: string | null,
) {
  const { data, error } = await apiClient.POST('/v1/api-keys', {
    params: { query: query({ project_id: projectId ?? undefined }) },
    body,
  })
  return unwrap<import('./types').CreatedApiKey>(data, error)
}

export async function revokeApiKey(
  keyId: string,
  projectId: string | null,
): Promise<void> {
  const { error } = await apiClient.DELETE('/v1/api-keys/{key_id}', {
    params: {
      path: { key_id: keyId },
      query: query({ project_id: projectId ?? undefined }),
    },
  })
  if (error) throw error
}

export async function getUsage(
  month: string | undefined,
  projectId: string | null,
): Promise<Usage> {
  const { data, error } = await apiClient.GET('/v1/usage', {
    params: { query: query({ month, project_id: projectId ?? undefined }) },
  })
  return unwrap<Usage>(data, error)
}

export async function createExport(
  body: { format: 'csv' | 'xlsx'; document_ids?: string[]; status?: string },
  projectId: string | null,
) {
  const { data, error } = await apiClient.POST('/v1/exports', {
    params: { query: query({ project_id: projectId ?? undefined }) },
    body,
  })
  return unwrap<import('./types').ExportJob>(data, error)
}

/** The page image and export download are plain URLs, not JSON. */
export function pageImageUrl(
  documentId: string,
  page: number,
  projectId: string | null,
): string {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''
  return `${API_ORIGIN}/v1/documents/${documentId}/pages/${page}/image${query}`
}

export function exportDownloadUrl(exportId: string, projectId: string | null): string {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''
  return `${API_ORIGIN}/v1/exports/${exportId}${query}`
}
