import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Check, Copy, FlaskConical, Pencil, X } from 'lucide-react'
import { toast } from 'sonner'
import {
  createTestRun,
  getContract,
  getSchema,
  listDocuments,
} from '../api/queries'
import { useAuth } from '../context/AuthContext'
import { Page } from '../components/layout/AppLayout'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Card, CardHeader } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Table'
import { CodeBlock } from '../components/CodeBlock'
import { SchemaBuilder } from './Schemas'
import { formatDate } from '../lib/format'
import { problemMessage } from '../lib/status'
import { cn } from '../lib/utils'

const MIN_TEST_DOCS = 3
const MAX_TEST_DOCS = 5

export default function SchemaDetail() {
  const { id = '' } = useParams()
  const { activeProjectId } = useAuth()
  const queryClient = useQueryClient()
  const [version, setVersion] = useState<number | null>(null)
  const [editing, setEditing] = useState(false)
  const [picked, setPicked] = useState<Set<string>>(new Set())

  const schemaQuery = useQuery({
    queryKey: ['schema', id, activeProjectId],
    queryFn: () => getSchema(id, activeProjectId),
    enabled: !!id,
  })

  const schema = schemaQuery.data
  const active = version ?? schema?.current_version ?? 1
  const activeVersion = schema?.versions?.find((v) => v.version === active)

  const contractQuery = useQuery({
    queryKey: ['contract', id, active, activeProjectId],
    queryFn: () => getContract(id, active, activeProjectId),
    enabled: !!id && !!schema,
  })

  const documentsQuery = useQuery({
    queryKey: ['documents', activeProjectId, ''],
    queryFn: () => listDocuments({ projectId: activeProjectId }),
  })

  const testRunMutation = useMutation({
    mutationFn: () => createTestRun(id, active, [...picked], activeProjectId),
    onSuccess: (run) => {
      toast[run.passed ? 'success' : 'warning'](
        run.passed ? 'Test run passed' : 'Test run did not pass',
        {
          description: run.passed
            ? 'A key can now be created for this version.'
            : 'Some documents did not produce every required field.',
        },
      )
      void queryClient.invalidateQueries({ queryKey: ['schema', id] })
    },
    onError: (error) =>
      toast.error('Test run failed', { description: problemMessage(error) }),
  })

  const documents = documentsQuery.data?.items ?? []
  const canRun = picked.size >= MIN_TEST_DOCS && picked.size <= MAX_TEST_DOCS
  const passed = activeVersion?.test_run_status === 'passed'

  if (schemaQuery.isLoading) {
    return (
      <Page title="Schema">
        <Skeleton className="h-40 w-full" />
      </Page>
    )
  }

  return (
    <Page
      title={schema?.name ?? 'Schema'}
      description={`${schema?.document_type ?? 'invoice'} · ${schema?.versions?.length ?? 0} version${schema?.versions?.length === 1 ? '' : 's'}`}
      action={
        <>
          {/* "Edit" is a new version, because a version an integration is
              pinned to must not change under it. The wording says so. */}
          <Button
            variant="secondary"
            onClick={() => setEditing(true)}
            disabled={!activeVersion || !!schema?.archived_at}
            title={
              schema?.archived_at
                ? 'Restore this schema before editing it'
                : undefined
            }
          >
            <Pencil className="h-3.5 w-3.5" />
            Edit fields
          </Button>
        <Link
          to="/app/schemas"
          className="inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-sm)] border px-3 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          All schemas
        </Link>
        </>
      }
    >
      {editing && activeVersion && (
        <div className="mb-5">
          <SchemaBuilder
            onClose={() => setEditing(false)}
            existing={{
              schemaId: id,
              fields: activeVersion.fields ?? [],
              dateOrder:
                (activeVersion.locale_hints as { date_order?: string } | null)
                  ?.date_order ?? 'DMY',
            }}
          />
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
        <div className="flex flex-col gap-4">
          <Card padded={false}>
            <div className="border-b px-4 py-3">
              <CardHeader title="Versions" description="Each version is immutable." />
            </div>
            <ul className="divide-y">
              {(schema?.versions ?? []).map((v) => (
                <li key={v.version}>
                  <button
                    onClick={() => setVersion(v.version)}
                    className={cn(
                      'flex w-full items-center justify-between gap-2 px-4 py-2.5 text-left transition-colors duration-100',
                      v.version === active
                        ? 'bg-[var(--surface-selected)]'
                        : 'hover:bg-[var(--surface-hover)]',
                    )}
                  >
                    <span>
                      <span className="text-sm font-medium text-[var(--text-primary)]">
                        Version {v.version}
                      </span>
                      <span className="mt-0.5 block text-xs text-[var(--text-tertiary)]">
                        {v.fields?.length ?? 0} fields · {formatDate(v.created_at)}
                      </span>
                    </span>
                    <Badge
                      tone={
                        v.test_run_status === 'passed'
                          ? 'success'
                          : v.test_run_status === 'failed'
                            ? 'danger'
                            : 'neutral'
                      }
                    >
                      {v.test_run_status === 'none' ? 'Not tested' : v.test_run_status}
                    </Badge>
                  </button>
                </li>
              ))}
            </ul>
          </Card>

          <Card padded={false}>
            <div className="border-b px-4 py-3">
              <CardHeader
                title="Test run"
                description={`Score version ${active} against ${MIN_TEST_DOCS}–${MAX_TEST_DOCS} documents you have already processed. A key cannot use a version until this passes.`}
              />
            </div>
            <div className="max-h-56 overflow-y-auto">
              {documents.length === 0 ? (
                <p className="px-4 py-5 text-sm text-[var(--text-tertiary)]">
                  Upload and process some documents first.
                </p>
              ) : (
                <ul className="divide-y">
                  {documents.map((doc) => (
                    <li key={doc.id}>
                      <label className="flex cursor-pointer items-center gap-2.5 px-4 py-2 hover:bg-[var(--surface-hover)]">
                        <input
                          type="checkbox"
                          checked={picked.has(doc.id)}
                          onChange={(e) =>
                            setPicked((current) => {
                              const next = new Set(current)
                              if (e.target.checked) next.add(doc.id)
                              else next.delete(doc.id)
                              return next
                            })
                          }
                          className="h-3.5 w-3.5 accent-[var(--accent-solid)]"
                        />
                        <span className="min-w-0 flex-1 truncate text-sm text-[var(--text-primary)]">
                          {doc.filename}
                        </span>
                        <span className="text-xs text-[var(--text-tertiary)]">
                          {doc.status.replace(/_/g, ' ')}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="flex items-center justify-between gap-2 border-t px-4 py-3">
              <span className="text-xs text-[var(--text-tertiary)]">
                {picked.size} of {MIN_TEST_DOCS}–{MAX_TEST_DOCS} chosen
              </span>
              <Button
                variant="primary"
                disabled={!canRun}
                loading={testRunMutation.isPending}
                onClick={() => testRunMutation.mutate()}
                title={!canRun ? `Choose ${MIN_TEST_DOCS} to ${MAX_TEST_DOCS} documents` : undefined}
              >
                <FlaskConical className="h-3.5 w-3.5" />
                Run test
              </Button>
            </div>

            {testRunMutation.data && (
              <div className="border-t px-4 py-3">
                <div className="mb-2 flex items-center gap-2">
                  {testRunMutation.data.passed ? (
                    <Check className="h-4 w-4 text-[var(--color-success-600)]" />
                  ) : (
                    <X className="h-4 w-4 text-[var(--color-danger-600)]" />
                  )}
                  <span className="text-sm font-medium text-[var(--text-primary)]">
                    {testRunMutation.data.passed ? 'Passed' : 'Did not pass'}
                  </span>
                </div>
                <ul className="flex flex-col gap-1">
                  {testRunMutation.data.per_document.map((row) => (
                    <li
                      key={row.document_id}
                      className="flex items-center justify-between gap-2 text-xs"
                    >
                      <span className="truncate text-[var(--text-secondary)]">
                        {documents.find((d) => d.id === row.document_id)?.filename ??
                          row.document_id}
                      </span>
                      <span className="tabular shrink-0 text-[var(--text-tertiary)]">
                        {row.fields_ok}/{row.fields_total} fields
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>
        </div>

        <Card padded={false}>
          <div className="flex items-center justify-between gap-2 border-b px-4 py-3">
            <CardHeader
              title={`Contract · version ${active}`}
              description="The JSON Schema your integration validates against. Give this to your developers."
            />
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                void navigator.clipboard.writeText(
                  JSON.stringify(contractQuery.data ?? {}, null, 2),
                )
                toast.success('Contract copied')
              }}
            >
              <Copy className="h-3.5 w-3.5" />
              Copy
            </Button>
          </div>
          <div className="max-h-[32rem] overflow-auto">
            {contractQuery.isLoading ? (
              <div className="p-4">
                <Skeleton className="h-64 w-full" />
              </div>
            ) : (
              <CodeBlock
                language="json"
                code={JSON.stringify(contractQuery.data ?? {}, null, 2)}
              />
            )}
          </div>
          {passed && (
            <div className="border-t px-4 py-3">
              <Link
                to="/app/api-keys"
                className="text-sm font-medium text-[var(--text-brand)] hover:underline"
              >
                Create an API key for this version →
              </Link>
            </div>
          )}
        </Card>
      </div>
    </Page>
  )
}
