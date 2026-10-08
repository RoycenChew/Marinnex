import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Archive,
  ArchiveRestore,
  Check,
  Plus,
  Search,
  Sparkles,
  Table2,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  addSchemaVersion,
  archiveSchema,
  createSchema,
  listSchemas,
  listTemplates,
  restoreSchema,
} from '../api/queries'
import type {
  CustomFieldInput,
  FieldConfigInput,
  SchemaSummary,
  TemplateField,
} from '../api/types'
import { useAuth } from '../context/AuthContext'
import { Page } from '../components/layout/AppLayout'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { ArrangerHeader, FieldArranger } from '../components/schema/FieldArranger'
import type { ArrangedField } from '../components/schema/FieldArranger'
import { CustomFieldPanel } from '../components/schema/CustomFieldPanel'
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
  const queryClient = useQueryClient()
  const [building, setBuilding] = useState(false)
  const [showArchived, setShowArchived] = useState(false)
  /* Two confirmations, because they are not the same act: archiving is
     reversible, purging is not, and a single dialog would have to be worded for
     the worse of the two. */
  const [pending, setPending] = useState<
    { schema: SchemaSummary; purge: boolean } | null
  >(null)

  const schemasQuery = useQuery({
    queryKey: ['schemas', activeProjectId, showArchived],
    queryFn: () => listSchemas(activeProjectId, showArchived),
  })

  const schemas = schemasQuery.data ?? []

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['schemas'] })
  }

  const archiveMutation = useMutation({
    mutationFn: ({ id, purge }: { id: string; purge: boolean }) =>
      archiveSchema(id, purge, activeProjectId),
    onSuccess: (_result, variables) => {
      toast.success(variables.purge ? 'Schema deleted' : 'Schema archived')
      setPending(null)
      refresh()
    },
    onError: (error) =>
      // The backend's refusal names what is still holding the schema, so it is
      // shown as-is rather than replaced with something vaguer.
      toast.error('Not deleted', { description: problemMessage(error) }),
  })

  const restoreMutation = useMutation({
    mutationFn: (id: string) => restoreSchema(id, activeProjectId),
    onSuccess: () => {
      toast.success('Schema restored')
      refresh()
    },
    onError: (error) =>
      toast.error('Not restored', { description: problemMessage(error) }),
  })

  return (
    <Page
      title="Schemas"
      description="A schema is the set of fields your integration receives, pinned to a version."
      action={
        <>
          <Button
            variant="ghost"
            onClick={() => setShowArchived((current) => !current)}
            aria-pressed={showArchived}
          >
            <Archive className="h-3.5 w-3.5" />
            {showArchived ? 'Hide archived' : 'Show archived'}
          </Button>
          <Button variant="primary" onClick={() => setBuilding(true)}>
            <Plus className="h-3.5 w-3.5" />
            New schema
          </Button>
        </>
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
            <TH width="92px" align="right">
              <span className="sr-only">Actions</span>
            </TH>
          </THead>
          {schemasQuery.isLoading ? (
            <TableSkeleton rows={3} columns={5} />
          ) : schemas.length === 0 ? (
            <TBody>
              <tr>
                <td colSpan={5}>
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
                    <span className="flex items-center gap-2">
                      <Link
                        to={`/app/schemas/${schema.schema_id}`}
                        className="font-medium text-[var(--text-primary)] hover:text-[var(--text-brand)]"
                      >
                        {schema.name}
                      </Link>
                      {schema.archived_at && <Badge tone="neutral">Archived</Badge>}
                    </span>
                  </TD>
                  <TD className="text-[var(--text-secondary)]">
                    {schema.document_type?.replace(/_/g, ' ') ?? 'invoice'}
                  </TD>
                  <TD numeric>v{schema.current_version}</TD>
                  <TD numeric title={schema.created_at ?? undefined} className="text-[var(--text-secondary)]">
                    {formatDate(schema.created_at)}
                  </TD>
                  <TD align="right">
                    <span className="flex items-center justify-end gap-0.5">
                      {schema.archived_at ? (
                        <>
                          <Button
                            size="icon"
                            variant="ghost"
                            aria-label={`Restore ${schema.name}`}
                            title="Restore"
                            loading={
                              restoreMutation.isPending &&
                              restoreMutation.variables === schema.schema_id
                            }
                            onClick={() => restoreMutation.mutate(schema.schema_id)}
                          >
                            <ArchiveRestore className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            aria-label={`Delete ${schema.name} permanently`}
                            title="Delete permanently"
                            onClick={() => setPending({ schema, purge: true })}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </>
                      ) : (
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label={`Archive ${schema.name}`}
                          title="Archive"
                          onClick={() => setPending({ schema, purge: false })}
                        >
                          <Archive className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </span>
                  </TD>
                </TR>
              ))}
            </TBody>
          )}
        </Table>
      </TableShell>

      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(open) => !open && setPending(null)}
        title={
          pending?.purge
            ? `Delete ${pending.schema.name} permanently?`
            : `Archive ${pending?.schema.name}?`
        }
        description={
          pending?.purge ? (
            <>
              This cannot be undone. It is refused if any extraction, job or live
              API key still refers to this schema — past results have to keep
              resolving the version they were produced against.
            </>
          ) : (
            <>
              It disappears from this list and accepts no new versions or test
              runs. Extractions already produced against it keep working, and you
              can restore it at any time.
            </>
          )
        }
        confirmLabel={pending?.purge ? 'Delete permanently' : 'Archive'}
        destructive={pending?.purge ?? false}
        loading={archiveMutation.isPending}
        onConfirm={() =>
          pending &&
          archiveMutation.mutate({
            id: pending.schema.schema_id,
            purge: pending.purge,
          })
        }
      />
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
  existing,
}: {
  onClose: () => void
  suggested?: string[]
  defaultName?: string
  /*
   * Present means "edit": a schema version cannot be changed in place, because
   * a customer's integration is pinned to it, so editing is adding a version.
   * The same picker does both — starting from the current version's fields
   * rather than an empty list, since an edit is usually a small change.
   */
  existing?: {
    schemaId: string
    fields: string[]
    dateOrder: string
    fieldConfig?: Record<string, FieldConfigInput>
    customFields?: CustomFieldInput[]
  }
}) {
  const { activeProjectId } = useAuth()
  const queryClient = useQueryClient()
  const [name, setName] = useState(defaultName)
  const [dateOrder, setDateOrder] = useState(existing?.dateOrder ?? 'DMY')
  const [search, setSearch] = useState('')
  const [picked, setPicked] = useState<Set<string>>(
    new Set(existing?.fields ?? suggested),
  )
  const [fieldConfig, setFieldConfig] = useState<Record<string, FieldConfigInput>>(
    existing?.fieldConfig ?? {},
  )
  const [customFields, setCustomFields] = useState<CustomFieldInput[]>(
    existing?.customFields ?? [],
  )

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

  /* The selected fields in the order they will arrive: explicit order first,
     then template order. Mirrors `SchemaSpec._order_of` so what is shown here
     is what the contract will say. */
  const arranged = useMemo<ArrangedField[]>(() => {
    const all: TemplateField[] = template?.fields ?? []
    const rows = all
      .filter((f) => picked.has(f.path) && !f.path.includes('[]'))
      .map((f) => ({
        path: f.path,
        label: f.label,
        requiredDefault: !!f.required_default,
      }))
    return rows.sort((a, b) => {
      const left = fieldConfig[a.path]?.order
      const right = fieldConfig[b.path]?.order
      if (left == null && right == null) return 0
      if (left == null) return 1
      if (right == null) return -1
      return left - right
    })
  }, [template, picked, fieldConfig])

  const createMutation = useMutation({
    mutationFn: () =>
      existing
        ? addSchemaVersion(
            existing.schemaId,
            {
              fields: [...picked],
              locale_hints: { date_order: dateOrder },
              field_config: fieldConfig,
              custom_fields: customFields,
            },
            activeProjectId,
          )
        : createSchema(
            {
              template_id: template?.id ?? 'tpl_invoice_v1',
              name: name.trim(),
              fields: [...picked],
              locale_hints: { date_order: dateOrder },
              field_config: fieldConfig,
              custom_fields: customFields,
            },
            activeProjectId,
          ),
    onSuccess: (result) => {
      toast.success(
        existing
          ? `Saved as version ${result.version}. Test it before a key can use it.`
          : `Created ${name} v${result.version}`,
      )
      void queryClient.invalidateQueries({ queryKey: ['schemas'] })
      void queryClient.invalidateQueries({ queryKey: ['schema'] })
      onClose()
    },
    onError: (error) =>
      toast.error('Not created', { description: problemMessage(error) }),
  })

  const canCreate = (existing ? true : name.trim().length > 0) && picked.size > 0

  return (
    <div className="mb-5 rounded-[var(--radius-lg)] border bg-[var(--surface-raised)] shadow-xs">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <h2 className="text-base font-semibold text-[var(--text-primary)]">
            {existing ? 'Edit fields' : 'New schema'}
          </h2>
          <p className="text-sm text-[var(--text-secondary)]">
            {existing
              ? 'Saved as a new version. The one your integrations already use does not change.'
              : 'Choose the fields your system needs. You can add a version later.'}
          </p>
        </div>
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </div>

      <div className="grid gap-4 border-b px-4 py-3 sm:grid-cols-2">
        <label className={cn('flex flex-col gap-1', existing && 'hidden')}>
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

      <div className="border-t">
        <ArrangerHeader />
        <FieldArranger
          fields={arranged}
          config={fieldConfig}
          onChange={setFieldConfig}
        />
      </div>

      <div className="border-t">
        <CustomFieldPanel fields={customFields} onChange={setCustomFields} />
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
          title={
            !canCreate
              ? existing
                ? 'Pick at least one field'
                : 'Name the schema and pick at least one field'
              : undefined
          }
        >
          <Check className="h-3.5 w-3.5" />
          {existing ? 'Save as new version' : 'Create schema'}
        </Button>
      </div>
    </div>
  )
}
