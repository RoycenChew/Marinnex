import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Group, Panel, Separator } from 'react-resizable-panels'
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  Download,
  History,
  Info,
  ScanLine,
  Sparkles,
  X,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  correctExtraction,
  decideExtraction,
  getAnalysis,
  getDocument,
  listExtractions,
} from '../api/queries'
import { API_ORIGIN } from '../api/client'
import type { Extraction } from '../api/types'
import { useAuth } from '../context/AuthContext'
import { Button } from '../components/ui/Button'
import { Skeleton } from '../components/ui/Table'
import { StatusBadge } from '../components/StatusBadge'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { PageViewer, boxesOf } from '../components/review/PageViewer'
import { FieldRow, LineItemGrid, groupFields } from '../components/review/FieldPanel'
import { formatDateTime } from '../lib/format'
import {
  SCAN_REVIEW_REASON,
  TYPE_MISMATCH_REASON,
  humaniseReason,
  problemMessage,
  statusMeta,
} from '../lib/status'
import { useMediaQuery } from '../lib/useMediaQuery'
import { cn } from '../lib/utils'

export default function DocumentAnalysis() {
  const { id = '' } = useParams()
  const { activeProjectId } = useAuth()
  const queryClient = useQueryClient()

  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [editingPath, setEditingPath] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState<Record<string, unknown>>({})
  const [historyOpen, setHistoryOpen] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const panelRef = useRef<HTMLDivElement>(null)
  /* A reviewer's own checklist for this sitting. There is no per-field endpoint
     — see BACKEND_REQUESTS.md — so this never leaves the browser, and the
     document-level decision remains the only thing the server is told. */
  const [checked, setChecked] = useState<Set<string>>(new Set())
  /* C10: below 768 px the split view has no room for two panes, so it becomes
     two tabs and selecting a value switches to the page. */
  const narrow = useMediaQuery('(max-width: 768px)')
  const [mobileTab, setMobileTab] = useState<'document' | 'information'>('information')

  const documentQuery = useQuery({
    queryKey: ['document', id, activeProjectId],
    queryFn: () => getDocument(id, activeProjectId),
    enabled: !!id,
    refetchInterval: (query) =>
      query.state.data?.status === 'processing' ? 2000 : false,
  })

  const analysisQuery = useQuery({
    queryKey: ['analysis', id, activeProjectId],
    queryFn: () => getAnalysis(id, activeProjectId),
    enabled: !!id,
    refetchInterval: (query) =>
      query.state.data?.status === 'processing' ? 2000 : false,
  })

  const versionsQuery = useQuery({
    queryKey: ['extractions', id, activeProjectId],
    queryFn: () => listExtractions(id, activeProjectId),
    enabled: historyOpen,
  })

  const extraction = analysisQuery.data
  // Memoised: `?? {}` produces a fresh object every render, which would defeat
  // every memo below it and re-derive the groups and boxes on each keystroke.
  const fields = useMemo(() => extraction?.fields ?? {}, [extraction])
  const groups = useMemo(() => groupFields(fields), [fields])
  const boxes = useMemo(() => boxesOf(fields), [fields])
  const scalarPaths = useMemo(
    () => groups.filter((g) => g.key !== 'lineItems').flatMap((g) => g.paths),
    [groups],
  )

  /*
   * The review queue: every field the backend flagged, in the order they appear
   * on screen, minus the ones this reviewer has already looked at. "Review
   * next" walks it, which is the difference between a list of problems and a
   * piece of work with an end.
   */
  const reviewQueue = useMemo(
    () =>
      groups
        .flatMap((group) => group.paths)
        .filter((path) => fields[path]?.status === 'needs_review'),
    [groups, fields],
  )
  const remaining = reviewQueue.filter((path) => !checked.has(path))

  /* C10: on a narrow screen, choosing a value means wanting to see it on the
     page, so selection moves to the document tab and its highlight. */
  const selectField = useCallback(
    (path: string | null) => {
      setSelectedPath(path)
      if (narrow && path) setMobileTab('document')
    },
    [narrow],
  )

  const reviewNext = useCallback(() => {
    const next =
      remaining.find((path) => path !== selectedPath) ?? remaining[0] ?? null
    if (!next) return
    setSelectedPath(next)
    window.requestAnimationFrame(() => {
      document.getElementById(`field-${next}`)?.scrollIntoView({ block: 'center' })
      if (narrow) setMobileTab('document')
    })
  }, [remaining, selectedPath, narrow])

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!extraction) throw new Error('Nothing loaded')
      const changes = Object.entries(pending).map(([path, value]) => ({ path, value }))
      return correctExtraction(extraction.extraction_id, changes, undefined, activeProjectId)
    },
    onSuccess: (next) => {
      setPending({})
      toast.success(`Saved as version ${next.version}`)
      void queryClient.invalidateQueries({ queryKey: ['analysis', id] })
      void queryClient.invalidateQueries({ queryKey: ['document', id] })
      void queryClient.invalidateQueries({ queryKey: ['extractions', id] })
    },
    onError: (error) =>
      toast.error('Not saved', { description: problemMessage(error) }),
  })

  const decideMutation = useMutation({
    mutationFn: async (input: { action: 'approve' | 'reject'; reason?: string }) => {
      if (!extraction) throw new Error('Nothing loaded')
      return decideExtraction(
        extraction.extraction_id,
        input.action,
        input.reason,
        activeProjectId,
      )
    },
    onSuccess: (result, input) => {
      toast.success(input.action === 'approve' ? 'Approved' : 'Rejected')
      void queryClient.invalidateQueries({ queryKey: ['analysis', id] })
      void queryClient.invalidateQueries({ queryKey: ['document', id] })
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      return result
    },
    onError: (error) =>
      toast.error('Not decided', { description: problemMessage(error) }),
  })

  const startEdit = useCallback(
    (path: string) => {
      const current = pending[path] ?? fields[path]?.value
      setDraft(current === null || current === undefined ? '' : String(current))
      setEditingPath(path)
    },
    [fields, pending],
  )

  const commitEdit = useCallback(() => {
    if (!editingPath) return
    setPending((current) => ({ ...current, [editingPath]: draft }))
    setEditingPath(null)
  }, [editingPath, draft])

  /*
   * Keyboard: J/K move, E edits, A approves. Skipped while an input has focus,
   * or typing "a" into a correction would approve the document.
   */
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return
      }
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const index = selectedPath ? scalarPaths.indexOf(selectedPath) : -1

      if (event.key === 'j' || event.key === 'k') {
        event.preventDefault()
        if (scalarPaths.length === 0) return
        const next =
          event.key === 'j'
            ? Math.min(index + 1, scalarPaths.length - 1)
            : Math.max(index - 1, 0)
        const path = scalarPaths[index === -1 ? 0 : next]
        setSelectedPath(path)
        document.getElementById(`field-${path}`)?.scrollIntoView({
          block: 'nearest',
        })
      }
      if (event.key === 'e' && selectedPath) {
        event.preventDefault()
        startEdit(selectedPath)
      }
      if (event.key === 'a' && extraction && extraction.status !== 'rejected') {
        event.preventDefault()
        if (Object.keys(pending).length > 0) {
          toast.warning('Save your changes before approving')
          return
        }
        decideMutation.mutate({ action: 'approve' })
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [selectedPath, scalarPaths, startEdit, extraction, pending, decideMutation])

  const doc = documentQuery.data
  const processing = extraction?.status === 'processing' || doc?.status === 'processing'
  const dirty = Object.keys(pending).length > 0
  const isScan = extraction?.reasons?.includes(SCAN_REVIEW_REASON)
  // Status on a pipeline call, reason on an interactive upload.
  const mismatch =
    extraction?.status === 'document_type_mismatch' ||
    !!extraction?.reasons?.includes(TYPE_MISMATCH_REASON)

  if (analysisQuery.isLoading || documentQuery.isLoading) {
    return <ReviewSkeleton />
  }

  if (analysisQuery.isError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
        <p className="text-base font-medium text-[var(--text-primary)]">
          Not found, or not in this project
        </p>
        <p className="max-w-sm text-sm text-[var(--text-secondary)]">
          {problemMessage(analysisQuery.error)}
        </p>
        <Link
          to="/app"
          className="inline-flex h-8 items-center rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-3 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--surface-hover)]"
        >
          Back to documents
        </Link>
      </div>
    )
  }

  const documentPane = (
    <>
        {doc && (
          <PageViewer
            documentId={id}
            projectId={activeProjectId}
            pageCount={doc.pages || 1}
            pageSizes={doc.page_sizes ?? {}}
            boxes={boxes}
            selectedPath={selectedPath}
            onSelectPath={selectField}
          />
        )}
    </>
  )

  const informationPane = (
    <>
        <div className="flex h-full flex-col bg-[var(--surface-raised)]">
          <div
            ref={panelRef}
            className="min-h-0 flex-1 overflow-y-auto"
          >
            {groups.map((group) => (
              <section key={group.key}>
                <h2 className="sticky top-0 z-10 border-b bg-[var(--surface-sunken)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)]">
                  {group.label}
                </h2>
                {group.key === 'lineItems' && extraction ? (
                  <LineItemGrid
                    extraction={extraction}
                    selectedPath={selectedPath}
                    onSelectPath={selectField}
                  />
                ) : (
                  <div className="divide-y">
                    {group.paths.map((path) => (
                      <FieldRow
                        key={path}
                        path={path}
                        entry={{
                          ...fields[path],
                          value:
                            path in pending ? pending[path] : fields[path].value,
                          status:
                            path in pending ? 'corrected' : fields[path].status,
                        }}
                        selected={selectedPath === path}
                        editing={editingPath === path}
                        draft={draft}
                        checked={checked.has(path)}
                        onSelect={() => selectField(path)}
                        onCheck={() =>
                          setChecked((current) => new Set(current).add(path))
                        }
                        onEdit={() => startEdit(path)}
                        onDraft={setDraft}
                        onCommit={commitEdit}
                        onCancel={() => setEditingPath(null)}
                      />
                    ))}
                  </div>
                )}
              </section>
            ))}
          </div>

          {/* Sticky action bar */}
          <div className="flex shrink-0 items-center justify-between gap-2 border-t bg-[var(--surface-raised)] px-3 py-2">
            <span className="text-xs text-[var(--text-tertiary)]">
              {dirty
                ? `${Object.keys(pending).length} unsaved change${Object.keys(pending).length === 1 ? '' : 's'}`
                : 'J/K move · E edit · A approve'}
            </span>
            <div className="flex items-center gap-2">
              {dirty && (
                <Button variant="ghost" size="sm" onClick={() => setPending({})}>
                  Discard
                </Button>
              )}
              <Button
                variant="secondary"
                size="sm"
                loading={saveMutation.isPending}
                disabled={!dirty}
                onClick={() => saveMutation.mutate()}
              >
                Save changes
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRejecting(true)}
                disabled={extraction?.status === 'rejected'}
              >
                <X className="h-3.5 w-3.5" />
                Reject
              </Button>
              <Button
                variant="primary"
                size="sm"
                // Never approve over unsaved edits: the approval would apply
                // to the version on the server, not the one on screen.
                disabled={dirty || extraction?.status === 'rejected'}
                loading={decideMutation.isPending}
                onClick={() => decideMutation.mutate({ action: 'approve' })}
                title={dirty ? 'Save your changes first' : undefined}
              >
                <Check className="h-3.5 w-3.5" />
                Approve
              </Button>
            </div>
          </div>
        </div>
    </>
  )

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b bg-[var(--surface-raised)] px-4 py-2.5">
        {/* Below `sm` the name takes its own row: sharing one with four
            controls left it no width at all and it disappeared. */}
        <div className="flex w-full min-w-0 items-center gap-3 sm:w-auto sm:flex-1">
          <Link
            to="/app"
            aria-label="Back to documents"
            className="rounded-[var(--radius-sm)] p-1 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold text-[var(--text-primary)]">
              {doc?.filename ?? 'Document'}
            </h1>
            <p className="truncate text-xs whitespace-nowrap text-[var(--text-tertiary)]">
              {doc?.document_type?.replace(/_/g, ' ') ?? 'unknown type'} ·{' '}
              {doc?.pages ?? 0} page{doc?.pages === 1 ? '' : 's'}
              {extraction ? ` · version ${extraction.version}` : ''}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <StatusBadge status={extraction?.status ?? doc?.status} code={doc?.error_code} />
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setHistoryOpen(true)}
            aria-label="Version history"
          >
            <History className="h-3.5 w-3.5" />
            History
          </Button>
          <a
            href={`${API_ORIGIN}/v1/documents/${id}/file`}
            className="inline-flex h-7 items-center gap-1.5 rounded-[var(--radius-sm)] border px-2.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
          >
            <Download className="h-3.5 w-3.5" />
            Original
          </a>
        </div>
      </div>

      {/* Banners */}
      {isScan && (
        <Banner
          tone="info"
          icon={<ScanLine className="h-4 w-4" />}
          title="Scanned documents are reviewed by a person before acceptance."
          body="This is routine for any scan, not a judgement about this file. OCR evidence is checked by hand until route B is measured."
        />
      )}
      {mismatch && (
        <Banner
          tone="danger"
          icon={<AlertTriangle className="h-4 w-4" />}
          title={
            doc?.document_type && doc.document_type !== 'unknown'
              ? `This doesn't look like an invoice — it looks like a ${doc.document_type.replace(/_/g, ' ')}.`
              : "This doesn't look like an invoice."
          }
          body={
            extraction?.status === 'document_type_mismatch'
              ? 'No data was extracted. Send it to a schema for its own document type.'
              : 'It was extracted anyway so you can see what was found, but it will not be accepted automatically.'
          }
        />
      )}
      {extraction?.status === 'needs_review' && !isScan && !mismatch && (
        <Banner
          tone="warning"
          icon={<Info className="h-4 w-4" />}
          title={statusMeta('needs_review').help}
          body={
            extraction.reasons.length > 0
              ? extraction.reasons.map(humaniseReason).join(' · ')
              : undefined
          }
        />
      )}

      {/* The work, with an end to it: how many values are waiting, and a way
          through them in the order they appear. */}
      {reviewQueue.length > 0 && !processing && (
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b bg-[var(--surface-raised)] px-4 py-2">
          <p className="text-sm text-[var(--text-primary)]">
            {remaining.length === 0 ? (
              <>
                You have been through all {reviewQueue.length} field
                {reviewQueue.length === 1 ? '' : 's'}. Approve when you are happy.
              </>
            ) : (
              <>
                <span className="font-medium">
                  {remaining.length} field{remaining.length === 1 ? '' : 's'} need
                  {remaining.length === 1 ? 's' : ''} your review
                </span>
                {checked.size > 0 && (
                  <span className="text-[var(--text-tertiary)]">
                    {' '}
                    · {checked.size} checked
                  </span>
                )}
              </>
            )}
          </p>
          {remaining.length > 0 && (
            <Button size="sm" variant="secondary" onClick={reviewNext}>
              Review next
            </Button>
          )}
        </div>
      )}

      {processing ? (
        <ProcessingState />
      ) : narrow ? (
        /* C10. Two panes do not fit below 768 px, so they become two tabs.
           Choosing a value on the Information tab moves to Document, where its
           highlight is. */
        <div className="flex min-h-0 flex-1 flex-col">
          <div
            role="tablist"
            aria-label="Document view"
            className="flex shrink-0 gap-0.5 border-b bg-[var(--surface-raised)] p-1"
          >
            {(['document', 'information'] as const).map((tab) => (
              <button
                key={tab}
                role="tab"
                aria-selected={mobileTab === tab}
                onClick={() => setMobileTab(tab)}
                className={cn(
                  'flex-1 rounded-[var(--radius-sm)] px-3 py-1.5 text-sm font-medium capitalize transition-colors',
                  mobileTab === tab
                    ? 'bg-[var(--surface-selected)] text-[var(--text-brand)]'
                    : 'text-[var(--text-secondary)]',
                )}
              >
                {tab}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1">
            {mobileTab === 'document' ? documentPane : informationPane}
          </div>
        </div>
      ) : (
        <Group orientation="horizontal" className="flex min-h-0 flex-1">
          <Panel defaultSize="56" minSize="30">
            {documentPane}
          </Panel>

          <Separator className="w-px shrink-0 cursor-col-resize bg-[var(--border-subtle)] transition-colors hover:bg-[var(--accent-solid)] data-[separator]:data-[active]:bg-[var(--accent-solid)]" />

          <Panel defaultSize="44" minSize="28">
            {informationPane}
          </Panel>
        </Group>
      )}

      {/* Version history drawer */}
      {historyOpen && (
        <div
          className="fixed inset-0 z-40 flex justify-end bg-[var(--color-slate-950)]/30"
          onClick={() => setHistoryOpen(false)}
        >
          <aside
            onClick={(e) => e.stopPropagation()}
            className="h-full w-80 overflow-y-auto border-l bg-[var(--surface-overlay)] p-4 shadow-lg"
          >
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">
                Version history
              </h2>
              <Button size="icon" variant="ghost" onClick={() => setHistoryOpen(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            {versionsQuery.isLoading && <Skeleton className="h-16 w-full" />}
            <ul className="flex flex-col gap-2">
              {(versionsQuery.data ?? []).map((version: Extraction) => (
                <li
                  key={version.extraction_id}
                  className={cn(
                    'rounded-[var(--radius-md)] border p-2.5',
                    version.extraction_id === extraction?.extraction_id &&
                      'border-[var(--accent-solid)] bg-[var(--surface-selected)]',
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-[var(--text-primary)]">
                      Version {version.version}
                    </span>
                    <StatusBadge status={version.status} />
                  </div>
                  <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                    {formatDateTime(version.created_at)}
                  </p>
                </li>
              ))}
            </ul>
          </aside>
        </div>
      )}

      <ConfirmDialog
        open={rejecting}
        onOpenChange={setRejecting}
        title="Reject this extraction?"
        destructive
        confirmLabel="Reject"
        description={
          <span className="block">
            A rejected extraction is read-only and cannot be corrected afterwards.
            A reason is required.
            <input
              autoFocus
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g. duplicate of INV-2026-0417"
              className="mt-3 w-full rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2 py-1.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
            />
          </span>
        }
        loading={decideMutation.isPending}
        onConfirm={() => {
          if (!rejectReason.trim()) {
            toast.error('A reason is required to reject')
            return
          }
          decideMutation.mutate({ action: 'reject', reason: rejectReason })
          setRejecting(false)
          setRejectReason('')
        }}
      />
    </div>
  )
}

function Banner({
  tone,
  icon,
  title,
  body,
}: {
  tone: 'info' | 'warning' | 'danger'
  icon: React.ReactNode
  title: string
  body?: string
}) {
  const tones = {
    info: 'bg-[var(--color-info-50)] text-[var(--color-info-700)] dark:bg-[var(--color-info-500)]/10 dark:text-[var(--color-info-500)]',
    warning:
      'bg-[var(--color-warning-50)] text-[var(--color-warning-700)] dark:bg-[var(--color-warning-500)]/10 dark:text-[var(--color-warning-500)]',
    danger:
      'bg-[var(--color-danger-50)] text-[var(--color-danger-700)] dark:bg-[var(--color-danger-500)]/10 dark:text-[var(--color-danger-400)]',
  }
  return (
    <div className={cn('flex shrink-0 items-start gap-2 border-b px-4 py-2', tones[tone])}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0">
        <p className="text-sm font-medium">{title}</p>
        {body && <p className="mt-0.5 text-xs opacity-90">{body}</p>}
      </div>
    </div>
  )
}

function ProcessingState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-10 text-center">
      <Sparkles className="h-6 w-6 animate-pulse text-[var(--text-tertiary)]" />
      <p className="text-base font-medium text-[var(--text-primary)]">
        Extracting this document
      </p>
      <p className="max-w-sm text-sm text-[var(--text-secondary)]">
        This page updates itself every couple of seconds. A one-page invoice
        usually takes under 15 seconds.
      </p>
    </div>
  )
}

/** Skeletons rather than a spinner, as the UI spec asks for this screen. */
function ReviewSkeleton() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b bg-[var(--surface-raised)] px-4 py-2.5">
        <Skeleton className="h-4 w-4" />
        <Skeleton className="h-4 w-48" />
      </div>
      <div className="flex min-h-0 flex-1">
        <div className="flex-1 bg-[var(--surface-sunken)] p-4">
          <Skeleton className="mx-auto h-full w-full max-w-xl" />
        </div>
        <div className="w-[44%] border-l bg-[var(--surface-raised)] p-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="mb-4">
              <Skeleton className="mb-1.5 h-3 w-24" />
              <Skeleton className="h-4 w-40" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
