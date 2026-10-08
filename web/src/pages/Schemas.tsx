import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Plus, Search, Sparkles, Table2 } from 'lucide-react'
import { toast } from 'sonner'
import { createSchema, listSchemas, listTemplates } from '../api/queries'
import type { TemplateField } from '../api/types'
import { useAuth } from '../context/AuthContext'
import { Page } from '../components/layout/AppLayout'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
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
import { cn } from '../lib/utils'

export default function Schemas() {
  const { activeProjectId } = useAuth()
  const [building, setBuilding] = useState(false)

  const schemasQuery = useQuery({
    queryKey: ['schemas', activeProjectId],
    queryFn: () => listSchemas(activeProjectId),
  })

  const schemas = schemasQuery.data ?? []

  return (
    <Page
      title="Schemas"
      description="A schema is the set of fields your integration receives, pinned to a version."
      action={
        <Button variant="primary" onClick={() => setBuilding(true)}>
          <Plus className="h-3.5 w-3.5" />
          New schema
        </Button>
      }
    >
      {building && (
        <SchemaBuilder onClose={() => setBuilding(false)} />
      )}

      <TableShell>
        <Table>
          <THead>
            <TH>Name</TH>
            <TH>Document type</TH>
            <TH align="right">Current version</TH>
            <TH align="right">Created</TH>
          </THead>
          {schemasQuery.isLoading ? (
            <TableSkeleton rows={3} columns={4} />
          ) : schemas.length === 0 ? (
            <TBody>
              <tr>
                <td colSpan={4}>
                  <EmptyState
                    icon={<Table2 className="h-5 w-5" />}
                    title="No schemas yet"
                    description="Pick the fields your system needs, test them on a few documents, then issue a key against the version."
                    action={
                      <Button variant="primary" onClick={() => setBuilding(true)}>
                        Create the first schema
                      </Button>
                    }
                  />
                </td>
              </tr>
            </TBody>
          ) : (
            <TBody>
              {schemas.map((schema) => (
                <TR key={schema.schema_id}>
                  <TD>
                    <Link
                      to={`/app/schemas/${schema.schema_id}`}
                      className="font-medium text-[var(--text-primary)] hover:text-[var(--text-brand)]"
                    >
                      {schema.name}
                    </Link>
                  </TD>
                  <TD className="text-[var(--text-secondary)]">
                    {schema.document_type?.replace(/_/g, ' ') ?? 'invoice'}
                  </TD>
                  <TD numeric>v{schema.current_version}</TD>
                  <TD numeric title={schema.created_at ?? undefined} className="text-[var(--text-secondary)]">
                    {formatDate(schema.created_at)}
                  </TD>
                </TR>
              ))}
            </TBody>
          )}
        </Table>
      </TableShell>
    </Page>
  )
}

/**
 * The field picker.
 *
 * Fields come from `GET /templates`, grouped by the prefix of their path so the
 * line-item columns sit together rather than being scattered through an
 * alphabetical list of twenty-six. `suggested` fields — the ones an analysis
 * actually grounded on a real document — are pre-ticked and labelled, because
 * "found in this document" is the only signal here that comes from evidence
 * rather than from a catalogue.
 */
export function SchemaBuilder({
  onClose,
  suggested = [],
  defaultName = '',
}: {
  onClose: () => void
  suggested?: string[]
  defaultName?: string
}) {
  const { activeProjectId } = useAuth()
  const queryClient = useQueryClient()
  const [name, setName] = useState(defaultName)
  const [dateOrder, setDateOrder] = useState('DMY')
  const [search, setSearch] = useState('')
  const [picked, setPicked] = useState<Set<string>>(new Set(suggested))

  const templatesQuery = useQuery({
    queryKey: ['templates', activeProjectId],
    queryFn: () => listTemplates(activeProjectId),
  })

  const template = templatesQuery.data?.[0]
  const groups = useMemo(() => {
    const fields: TemplateField[] = template?.fields ?? []
    const match = search.trim().toLowerCase()
    const visible = match
      ? fields.filter(
          (f) =>
            f.label.toLowerCase().includes(match) ||
            f.path.toLowerCase().includes(match),
        )
      : fields
    const scalar = visible.filter((f) => !f.path.includes('[]'))
    const lineItems = visible.filter((f) => f.path.includes('[]'))
    return [
      { label: 'Document fields', fields: scalar },
      { label: 'Line-item columns', fields: lineItems },
    ].filter((g) => g.fields.length > 0)
  }, [template, search])

  const createMutation = useMutation({
    mutationFn: () =>
      createSchema(
        {
          template_id: template?.id ?? 'tpl_invoice_v1',
          name: name.trim(),
          fields: [...picked],
          locale_hints: { date_order: dateOrder },
        },
        activeProjectId,
      ),
    onSuccess: (result) => {
      toast.success(`Created ${name} v${result.version}`)
      void queryClient.invalidateQueries({ queryKey: ['schemas'] })
      onClose()
    },
    onError: (error) =>
      toast.error('Not created', { description: problemMessage(error) }),
  })

  const canCreate = name.trim().length > 0 && picked.size > 0

  return (
    <div className="mb-5 rounded-[var(--radius-lg)] border bg-[var(--surface-raised)] shadow-xs">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <h2 className="text-base font-semibold text-[var(--text-primary)]">
            New schema
          </h2>
          <p className="text-sm text-[var(--text-secondary)]">
            Choose the fields your system needs. You can add a version later.
          </p>
        </div>
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </div>

      <div className="grid gap-4 border-b px-4 py-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--text-secondary)]">
            Schema name
          </span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="AP invoices"
            className="rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2.5 py-1.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--text-secondary)]">
            Date order
          </span>
          <select
            value={dateOrder}
            onChange={(e) => setDateOrder(e.target.value)}
            className="rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2.5 py-1.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
          >
            <option value="DMY">Day first — 03/10/2026 is 3 October</option>
            <option value="MDY">Month first — 03/10/2026 is 10 March</option>
            <option value="YMD">Year first</option>
          </select>
        </label>
      </div>

      <div className="flex items-center justify-between gap-3 border-b px-4 py-2">
        <div className="relative max-w-xs flex-1">
          <Search className="absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-tertiary)]" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Find a field"
            className="w-full rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] py-1.5 pr-2.5 pl-8 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
          />
        </div>
        <span className="tabular text-xs text-[var(--text-tertiary)]">
          {picked.size} selected
        </span>
      </div>

      <div className="max-h-96 overflow-y-auto">
        {templatesQuery.isLoading && (
          <p className="px-4 py-6 text-sm text-[var(--text-tertiary)]">
            Loading the template…
          </p>
        )}
        {groups.map((group) => (
          <section key={group.label}>
            <h3 className="sticky top-0 border-b bg-[var(--surface-sunken)] px-4 py-1.5 text-xs font-medium text-[var(--text-secondary)]">
              {group.label}
            </h3>
            <ul className="divide-y">
              {group.fields.map((field) => {
                const isPicked = picked.has(field.path)
                const wasFound = suggested.includes(field.path)
                return (
                  <li key={field.path}>
                    <label
                      className={cn(
                        'flex cursor-pointer items-start gap-2.5 px-4 py-2 transition-colors duration-100',
                        isPicked
                          ? 'bg-[var(--surface-selected)]'
                          : 'hover:bg-[var(--surface-hover)]',
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={isPicked}
                        onChange={(e) =>
                          setPicked((current) => {
                            const next = new Set(current)
                            if (e.target.checked) next.add(field.path)
                            else next.delete(field.path)
                            return next
                          })
                        }
                        className="mt-0.5 h-3.5 w-3.5 accent-[var(--accent-solid)]"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-1.5">
                          <span className="text-sm font-medium text-[var(--text-primary)]">
                            {field.label}
                          </span>
                          {wasFound && (
                            <Badge tone="success" icon={<Sparkles className="h-2.5 w-2.5" />}>
                              Found in this document
                            </Badge>
                          )}
                          {field.required_default && (
                            <Badge tone="neutral">Required</Badge>
                          )}
                        </span>
                        <span className="mt-0.5 block text-xs text-[var(--text-tertiary)]">
                          {field.description}
                        </span>
                      </span>
                    </label>
                  </li>
                )
              })}
            </ul>
          </section>
        ))}
      </div>

      <div className="flex items-center justify-end gap-2 border-t px-4 py-3">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button
          variant="primary"
          disabled={!canCreate}
          loading={createMutation.isPending}
          onClick={() => createMutation.mutate()}
          title={!canCreate ? 'Name the schema and pick at least one field' : undefined}
        >
          <Check className="h-3.5 w-3.5" />
          Create schema
        </Button>
      </div>
    </div>
  )
}
