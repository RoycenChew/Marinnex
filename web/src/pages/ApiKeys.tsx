import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as Dialog from '@radix-ui/react-dialog'
import * as Tabs from '@radix-ui/react-tabs'
import { AlertTriangle, Copy, KeyRound, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  createApiKey,
  listApiKeys,
  listSchemas,
  revokeApiKey,
} from '../api/queries'
import { API_ORIGIN } from '../api/client'
import type { ApiKey, CreatedApiKey } from '../api/types'
import { useAuth } from '../context/AuthContext'
import { Page } from '../components/layout/AppLayout'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Card, CardHeader } from '../components/ui/Card'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { CodeBlock } from '../components/CodeBlock'
import {
  EmptyState,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  TableShell,
  TableSkeleton,
} from '../components/ui/Table'
import { formatDate } from '../lib/format'
import { problemMessage } from '../lib/status'

/**
 * Derived because the API does not send it.
 *
 * `GET /v1/api-keys` returns `expires_at`, `revoked_at` and `last_used_at` but no
 * single state, so every client re-implements this comparison. Logged in
 * BACKEND_REQUESTS.md as a request for a `status` field.
 */
function keyState(key: ApiKey): { label: string; tone: 'success' | 'neutral' | 'danger' } {
  if (key.revoked_at) return { label: 'Revoked', tone: 'danger' }
  if (key.expires_at && new Date(key.expires_at) <= new Date()) {
    return { label: 'Expired', tone: 'neutral' }
  }
  return { label: 'Active', tone: 'success' }
}

export default function ApiKeys() {
  const { activeProjectId } = useAuth()
  const queryClient = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [issued, setIssued] = useState<CreatedApiKey | null>(null)
  const [revoking, setRevoking] = useState<ApiKey | null>(null)

  const keysQuery = useQuery({
    queryKey: ['apiKeys', activeProjectId],
    queryFn: () => listApiKeys(activeProjectId),
  })
  const schemasQuery = useQuery({
    queryKey: ['schemas', activeProjectId],
    queryFn: () => listSchemas(activeProjectId),
  })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => revokeApiKey(id, activeProjectId),
    onSuccess: () => {
      toast.success('Key revoked')
      void queryClient.invalidateQueries({ queryKey: ['apiKeys'] })
    },
    onError: (error) =>
      toast.error('Not revoked', { description: problemMessage(error) }),
  })

  const keys = keysQuery.data ?? []
  const schemas = schemasQuery.data ?? []

  return (
    <Page
      title="API keys"
      description="Keys let your own systems send documents to the pipeline and get the same JSON back."
      action={
        <Button variant="primary" onClick={() => setCreating(true)}>
          <Plus className="h-3.5 w-3.5" />
          Create key
        </Button>
      }
    >
      <TableShell className="mb-5">
        <Table>
          <THead>
            <TH>Name</TH>
            <TH>Prefix</TH>
            <TH>Mode</TH>
            <TH>Status</TH>
            <TH align="right">Created</TH>
            <TH align="right">Last used</TH>
            <TH width="56px" align="right">
              <span className="sr-only">Actions</span>
            </TH>
          </THead>
          {keysQuery.isLoading ? (
            <TableSkeleton rows={3} columns={7} />
          ) : keys.length === 0 ? (
            <TBody>
              <tr>
                <td colSpan={7}>
                  <EmptyState
                    icon={<KeyRound className="h-5 w-5" />}
                    title="No keys yet"
                    description="A test key costs nothing to use and never reaches the live provider."
                    action={
                      <Button variant="primary" onClick={() => setCreating(true)}>
                        Create a key
                      </Button>
                    }
                  />
                </td>
              </tr>
            </TBody>
          ) : (
            <TBody>
              {keys.map((key) => {
                const state = keyState(key)
                return (
                  <TR key={key.id}>
                    <TD className="font-medium">{key.name}</TD>
                    <TD>
                      <code className="rounded-[var(--radius-xs)] bg-[var(--surface-sunken)] px-1.5 py-0.5 text-xs">
                        {key.prefix}…
                      </code>
                    </TD>
                    <TD>
                      <Badge tone={key.mode === 'live' ? 'brand' : 'neutral'}>
                        {key.mode}
                      </Badge>
                    </TD>
                    <TD>
                      <Badge tone={state.tone}>{state.label}</Badge>
                    </TD>
                    <TD numeric className="text-[var(--text-secondary)]">
                      {formatDate(key.created_at)}
                    </TD>
                    <TD numeric className="text-[var(--text-secondary)]">
                      {key.last_used_at ? formatDate(key.last_used_at) : 'Never'}
                    </TD>
                    <TD align="right">
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label={`Revoke ${key.name}`}
                        disabled={!!key.revoked_at}
                        onClick={() => setRevoking(key)}
                        className="text-[var(--text-tertiary)] hover:text-[var(--color-danger-600)]"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TD>
                  </TR>
                )
              })}
            </TBody>
          )}
        </Table>
      </TableShell>

      <DeveloperPanel schemas={schemas} />

      <CreateKeyDialog
        open={creating}
        onOpenChange={setCreating}
        schemas={schemas}
        onCreated={(key) => {
          setIssued(key)
          setCreating(false)
          void queryClient.invalidateQueries({ queryKey: ['apiKeys'] })
        }}
      />

      <RevealDialog issued={issued} onClose={() => setIssued(null)} />

      <ConfirmDialog
        open={revoking !== null}
        onOpenChange={(open) => !open && setRevoking(null)}
        title={`Revoke ${revoking?.name}?`}
        description="Any system still using this key starts getting 401 immediately. This cannot be undone; issue a new key instead."
        confirmLabel="Revoke key"
        loading={revokeMutation.isPending}
        onConfirm={() => {
          if (revoking) revokeMutation.mutate(revoking.id)
          setRevoking(null)
        }}
      />
    </Page>
  )
}

function CreateKeyDialog({
  open,
  onOpenChange,
  schemas,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  schemas: { schema_id: string; name: string; current_version: number }[]
  onCreated: (key: CreatedApiKey) => void
}) {
  const { activeProjectId } = useAuth()
  const [name, setName] = useState('')
  const [mode, setMode] = useState<'live' | 'test'>('test')
  const [picked, setPicked] = useState<Set<string>>(new Set())

  const mutation = useMutation({
    mutationFn: () =>
      createApiKey(
        {
          name: name.trim(),
          mode,
          schema_versions: [...picked].map((entry) => {
            const [schema_id, version] = entry.split('@')
            return { schema_id, version: Number(version) }
          }),
        },
        activeProjectId,
      ),
    onSuccess: (key) => {
      setName('')
      setPicked(new Set())
      onCreated(key)
    },
    onError: (error) =>
      toast.error('Key not created', { description: problemMessage(error) }),
  })

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[var(--color-slate-950)]/40 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-[min(30rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius-lg)] border bg-[var(--surface-overlay)] p-5 shadow-lg">
          <Dialog.Title className="text-base font-semibold text-[var(--text-primary)]">
            Create an API key
          </Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-[var(--text-secondary)]">
            The key is shown once, when it is created.
          </Dialog.Description>

          <label className="mt-4 flex flex-col gap-1">
            <span className="text-xs font-medium text-[var(--text-secondary)]">
              Name
            </span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Accounts payable integration"
              className="rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2.5 py-1.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
            />
          </label>

          <div className="mt-3">
            <span className="text-xs font-medium text-[var(--text-secondary)]">Mode</span>
            <div className="mt-1 flex gap-2">
              {(['test', 'live'] as const).map((option) => (
                <button
                  key={option}
                  onClick={() => setMode(option)}
                  className={
                    'flex-1 rounded-[var(--radius-sm)] border px-3 py-2 text-left text-sm transition-colors ' +
                    (mode === option
                      ? 'border-[var(--accent-solid)] bg-[var(--surface-selected)]'
                      : 'hover:bg-[var(--surface-hover)]')
                  }
                >
                  <span className="block font-medium text-[var(--text-primary)]">
                    {option === 'test' ? 'Test' : 'Live'}
                  </span>
                  <span className="mt-0.5 block text-xs text-[var(--text-tertiary)]">
                    {option === 'test'
                      ? 'Never reaches the paid provider'
                      : 'Real extractions, billed'}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="mt-3">
            <span className="text-xs font-medium text-[var(--text-secondary)]">
              Schema versions this key may use
            </span>
            <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
              Leave empty to allow every version in this project.
            </p>
            <ul className="mt-1.5 max-h-32 overflow-y-auto rounded-[var(--radius-sm)] border">
              {schemas.length === 0 && (
                <li className="px-3 py-2 text-xs text-[var(--text-tertiary)]">
                  No schemas yet.
                </li>
              )}
              {schemas.map((schema) => {
                const value = `${schema.schema_id}@${schema.current_version}`
                return (
                  <li key={value}>
                    <label className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm hover:bg-[var(--surface-hover)]">
                      <input
                        type="checkbox"
                        checked={picked.has(value)}
                        onChange={(e) =>
                          setPicked((current) => {
                            const next = new Set(current)
                            if (e.target.checked) next.add(value)
                            else next.delete(value)
                            return next
                          })
                        }
                        className="h-3.5 w-3.5 accent-[var(--accent-solid)]"
                      />
                      <span className="text-[var(--text-primary)]">
                        {schema.name}{' '}
                        <span className="text-[var(--text-tertiary)]">
                          v{schema.current_version}
                        </span>
                      </span>
                    </label>
                  </li>
                )
              })}
            </ul>
          </div>

          <div className="mt-5 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button variant="secondary">Cancel</Button>
            </Dialog.Close>
            <Button
              variant="primary"
              disabled={!name.trim()}
              loading={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              Create key
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

/** The one-time reveal. There is no second chance, so the dialog says so. */
function RevealDialog({
  issued,
  onClose,
}: {
  issued: CreatedApiKey | null
  onClose: () => void
}) {
  return (
    <Dialog.Root open={issued !== null} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[var(--color-slate-950)]/50 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius-lg)] border bg-[var(--surface-overlay)] p-5 shadow-lg">
          <Dialog.Title className="text-base font-semibold text-[var(--text-primary)]">
            Copy your key now
          </Dialog.Title>
          <div className="mt-3 flex items-start gap-2 rounded-[var(--radius-md)] bg-[var(--color-warning-50)] p-3 text-sm text-[var(--color-warning-700)] dark:bg-[var(--color-warning-500)]/10 dark:text-[var(--color-warning-500)]">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <p>
              This is the only time the key is shown. Only a hash is stored, so it
              cannot be recovered — if you lose it, revoke it and create another.
            </p>
          </div>
          <div className="mt-3 flex items-center gap-2 rounded-[var(--radius-sm)] border bg-[var(--surface-sunken)] p-2.5">
            <code className="min-w-0 flex-1 overflow-x-auto font-mono text-xs text-[var(--text-primary)]">
              {issued?.key}
            </code>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                if (issued) void navigator.clipboard.writeText(issued.key)
                toast.success('Key copied to the clipboard')
              }}
            >
              <Copy className="h-3.5 w-3.5" />
              Copy
            </Button>
          </div>
          <div className="mt-5 flex justify-end">
            <Button variant="primary" onClick={onClose}>
              I have stored it
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

/** Ready-to-paste calls for the pipeline endpoint. */
function DeveloperPanel({
  schemas,
}: {
  schemas: { schema_id: string; name: string; current_version: number }[]
}) {
  const [selected, setSelected] = useState(0)
  const schema = schemas[selected]
  const schemaId = schema?.schema_id ?? 'sch_…'
  const version = schema?.current_version ?? 1

  const samples = useMemo(
    () => ({
      curl: `curl -X POST "${API_ORIGIN}/v1/extract?wait=30" \\
  -H "Authorization: Bearer fdip_test_YOUR_KEY" \\
  -F "file=@invoice.pdf" \\
  -F "schema_id=${schemaId}" \\
  -F "schema_version=${version}"`,
      python: `import requests

with open("invoice.pdf", "rb") as handle:
    response = requests.post(
        "${API_ORIGIN}/v1/extract",
        params={"wait": 30},
        headers={"Authorization": "Bearer fdip_test_YOUR_KEY"},
        files={"file": handle},
        data={"schema_id": "${schemaId}", "schema_version": ${version}},
        timeout=60,
    )

response.raise_for_status()
result = response.json()
# Decimals arrive as strings; keep them that way.
print(result["status"], result["data"]["total"])`,
      javascript: `const body = new FormData()
body.append('file', file)
body.append('schema_id', '${schemaId}')
body.append('schema_version', '${version}')

const response = await fetch('${API_ORIGIN}/v1/extract?wait=30', {
  method: 'POST',
  headers: { Authorization: 'Bearer fdip_test_YOUR_KEY' },
  body,
})

const result = await response.json()
// 200 means it finished inside the wait; 202 means poll /v1/extractions/{id}.
console.log(response.status, result.status)`,
    }),
    [schemaId, version],
  )

  return (
    <Card padded={false}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <CardHeader
          title="Call the pipeline"
          description="Send a document from your own system and get the same JSON this UI shows."
        />
        {schemas.length > 1 && (
          <select
            value={selected}
            onChange={(e) => setSelected(Number(e.target.value))}
            className="rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2 py-1 text-sm text-[var(--text-primary)]"
          >
            {schemas.map((s, index) => (
              <option key={s.schema_id} value={index}>
                {s.name} v{s.current_version}
              </option>
            ))}
          </select>
        )}
      </div>

      <Tabs.Root defaultValue="curl">
        <Tabs.List className="flex gap-0.5 border-b px-3 pt-2">
          {[
            ['curl', 'cURL'],
            ['python', 'Python'],
            ['javascript', 'JavaScript'],
          ].map(([value, label]) => (
            <Tabs.Trigger
              key={value}
              value={value}
              className="rounded-t-[var(--radius-sm)] px-3 py-1.5 text-sm font-medium text-[var(--text-secondary)] data-[state=active]:bg-[var(--surface-sunken)] data-[state=active]:text-[var(--text-primary)]"
            >
              {label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        {(['curl', 'python', 'javascript'] as const).map((value) => (
          <Tabs.Content key={value} value={value} className="relative">
            <Button
              size="sm"
              variant="secondary"
              className="absolute top-2 right-2 z-10"
              onClick={() => {
                void navigator.clipboard.writeText(samples[value])
                toast.success('Copied')
              }}
            >
              <Copy className="h-3.5 w-3.5" />
              Copy
            </Button>
            <CodeBlock
              code={samples[value]}
              language={value === 'curl' ? 'bash' : value}
            />
          </Tabs.Content>
        ))}
      </Tabs.Root>
    </Card>
  )
}
