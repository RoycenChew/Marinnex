/**
 * The API calls, in one place.
 *
 * This file used to exist for its casts: `?project_id=` was accepted by the
 * backend but undeclared in `openapi.json`, and every response was typed
 * `{[key: string]: unknown}` because the handlers returned bare dicts. Both are
 * fixed — the parameter is declared on the session dependency and every route
 * carries a response model — so what remains is a plain typed façade with no
 * casts in it.
 *
 * Keeping the façade is deliberate: a screen should say `listDocuments(...)`
 * rather than repeat a path, a params object and an error check each time.
 */
import { API_ORIGIN, apiClient } from './client'
import type {
  ApiKey,
  CreatedApiKey,
  DocumentDetail,
  DocumentList,
  ExportJob,
  Extraction,
  SchemaCreated,
  SchemaSummary,
  Template,
  TestRun,
  Usage,
} from './types'

/** Throw the RFC 9457 problem so TanStack Query surfaces it as an error. */
function unwrap<T>(data: T | undefined, error: unknown): T {
  if (error) throw error
  return data as T
}

/** `null` means "the caller's first project", which the backend defaults to. */
const project = (id: string | null) => id ?? undefined

export async function listDocuments(options: {
  projectId: string | null
  status?: string
  limit?: number
  cursor?: string
}): Promise<DocumentList> {
  const { data, error } = await apiClient.GET('/v1/documents', {
    params: {
      query: {
        project_id: project(options.projectId),
        status: options.status,
        limit: options.limit ?? 100,
        cursor: options.cursor,
      },
    },
  })
  return unwrap(data, error)
}

export async function getDocument(
  id: string,
  projectId: string | null,
): Promise<DocumentDetail> {
  const { data, error } = await apiClient.GET('/v1/documents/{document_id}', {
    params: { path: { document_id: id }, query: { project_id: project(projectId) } },
  })
  return unwrap(data, error)
}

export async function deleteDocument(
  id: string,
  projectId: string | null,
): Promise<void> {
  const { error } = await apiClient.DELETE('/v1/documents/{document_id}', {
    params: { path: { document_id: id }, query: { project_id: project(projectId) } },
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
        query: { project_id: project(projectId) },
      },
    },
  )
  // The route returns either a finished extraction or the pending placeholder;
  // callers branch on `status`, and the placeholder carries the same keys.
  return unwrap(data, error) as Extraction
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
        query: { project_id: project(projectId) },
      },
    },
  )
  return unwrap(data, error)
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
        query: { project_id: project(projectId) },
      },
      body: { changes, reason },
    },
  )
  return unwrap(data, error)
}

/**
 * Which fields a reviewer has already been through on this extraction.
 *
 * Persisted server-side as audit events, so the "N fields need your review"
 * count survives a reload — it used to live in React state and was lost on
 * refresh, halfway down a long invoice.
 */
export async function listFieldReviews(
  extractionId: string,
  projectId: string | null,
) {
  const { data, error } = await apiClient.GET(
    '/v1/extractions/{extraction_id}/field-reviews',
    {
      params: {
        path: { extraction_id: extractionId },
        query: { project_id: project(projectId) },
      },
    },
  )
  return unwrap(data, error)
}

export async function setFieldReviewed(
  extractionId: string,
  path: string,
  checked: boolean,
  projectId: string | null,
) {
  const request = {
    params: {
      path: { extraction_id: extractionId },
      query: { project_id: project(projectId) },
    },
    body: { path },
  }
  const { data, error } = checked
    ? await apiClient.POST('/v1/extractions/{extraction_id}/field-reviews', request)
    : await apiClient.DELETE('/v1/extractions/{extraction_id}/field-reviews', request)
  return unwrap(data, error)
}

export async function decideExtraction(
  extractionId: string,
  action: 'approve' | 'reject',
  reason: string | undefined,
  projectId: string | null,
) {
  const { data, error } = await apiClient.POST(
    '/v1/extractions/{extraction_id}/decision',
    {
      params: {
        path: { extraction_id: extractionId },
        query: { project_id: project(projectId) },
      },
      body: { action, reason },
    },
  )
  return unwrap(data, error)
}

export async function listTemplates(projectId: string | null): Promise<Template[]> {
  const { data, error } = await apiClient.GET('/v1/templates', {
    params: { query: { project_id: project(projectId) } },
  })
  return unwrap(data, error)
}

export async function listSchemas(
  projectId: string | null,
): Promise<SchemaSummary[]> {
  const { data, error } = await apiClient.GET('/v1/schemas', {
    params: { query: { project_id: project(projectId) } },
  })
  return unwrap(data, error)
}

export async function getSchema(
  id: string,
  projectId: string | null,
): Promise<SchemaSummary> {
  const { data, error } = await apiClient.GET('/v1/schemas/{schema_id}', {
    params: { path: { schema_id: id }, query: { project_id: project(projectId) } },
  })
  return unwrap(data, error)
}

export async function createSchema(
  body: {
    template_id: string
    name: string
    fields: string[]
    locale_hints: { date_order: string }
  },
  projectId: string | null,
): Promise<SchemaCreated> {
  const { data, error } = await apiClient.POST('/v1/schemas', {
    params: { query: { project_id: project(projectId) } },
    body,
  })
  return unwrap(data, error)
}

export async function addSchemaVersion(
  schemaId: string,
  body: { fields: string[]; locale_hints: { date_order: string } },
  projectId: string | null,
): Promise<SchemaCreated> {
  const { data, error } = await apiClient.POST('/v1/schemas/{schema_id}/versions', {
    params: {
      path: { schema_id: schemaId },
      query: { project_id: project(projectId) },
    },
    body,
  })
  return unwrap(data, error)
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
        query: { project_id: project(projectId) },
      },
    },
  )
  // Genuinely free-form: this *is* a JSON Schema, so it has no fixed shape.
  return unwrap(data, error)
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
        query: { project_id: project(projectId) },
      },
      body: { document_ids: documentIds },
    },
  )
  return unwrap(data, error)
}

export async function getTestRun(
  runId: string,
  projectId: string | null,
): Promise<TestRun> {
  const { data, error } = await apiClient.GET('/v1/test-runs/{run_id}', {
    params: { path: { run_id: runId }, query: { project_id: project(projectId) } },
  })
  return unwrap(data, error)
}

export async function listApiKeys(projectId: string | null): Promise<ApiKey[]> {
  const { data, error } = await apiClient.GET('/v1/api-keys', {
    params: { query: { project_id: project(projectId) } },
  })
  return unwrap(data, error)
}

export async function createApiKey(
  body: {
    name: string
    mode: 'live' | 'test'
    schema_versions: { schema_id: string; version: number }[]
    expires_at?: string | null
  },
  projectId: string | null,
): Promise<CreatedApiKey> {
  const { data, error } = await apiClient.POST('/v1/api-keys', {
    params: { query: { project_id: project(projectId) } },
    body,
  })
  return unwrap(data, error)
}

export async function revokeApiKey(
  keyId: string,
  projectId: string | null,
): Promise<void> {
  const { error } = await apiClient.DELETE('/v1/api-keys/{key_id}', {
    params: { path: { key_id: keyId }, query: { project_id: project(projectId) } },
  })
  if (error) throw error
}

export async function getUsage(
  month: string | undefined,
  projectId: string | null,
): Promise<Usage> {
  const { data, error } = await apiClient.GET('/v1/usage', {
    params: { query: { month, project_id: project(projectId) } },
  })
  return unwrap(data, error)
}

export async function createExport(
  body: { format: 'csv' | 'xlsx'; document_ids?: string[]; status?: string },
  projectId: string | null,
): Promise<ExportJob> {
  const { data, error } = await apiClient.POST('/v1/exports', {
    params: { query: { project_id: project(projectId) } },
    body,
  })
  return unwrap(data, error)
}

/** The page image and the export download are plain URLs, not JSON. */
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
