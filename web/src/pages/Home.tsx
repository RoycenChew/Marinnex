import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  CircleCheck,
  Coins,
  FileText,
  Inbox,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import { deleteDocument, listDocuments, getUsage } from '../api/queries'
import type { DocumentListItem } from '../api/types'
import { useAuth } from '../context/AuthContext'
import { Page } from '../components/layout/AppLayout'
import { StatCard } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
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
  type SortDirection,
} from '../components/ui/Table'
import { StatusBadge } from '../components/StatusBadge'
import { UploadZone } from '../components/UploadZone'
import { Welcome } from '../components/onboarding/Welcome'
import { Tour } from '../components/onboarding/Tour'
import { hasSeenTour, markTourSeen } from '../lib/onboarding'
import { formatCost, formatDate, formatPercent } from '../lib/format'
import { problemMessage } from '../lib/status'
import { cn } from '../lib/utils'

type DocumentRow = DocumentListItem

const FILTERS = [
  { value: '', label: 'All' },
  { value: 'needs_review', label: 'Needs review' },
  { value: 'completed', label: 'Completed' },
  { value: 'processing', label: 'Processing' },
] as const

type SortKey = 'filename' | 'status' | 'created_at'

export default function Home() {
  const { activeProjectId, user } = useAuth()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<string>('')
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection }>({
    key: 'created_at',
    direction: 'desc',
  })
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [pendingDelete, setPendingDelete] = useState<DocumentRow | null>(null)
  const [tourOpen, setTourOpen] = useState(false)
  const [welcomeDismissed, setWelcomeDismissed] = useState(false)
  /* `hasSeenTour` reads storage, which does not re-render on write, so the
     answer is held in state and updated alongside it. */
  const [tourOffered, setTourOffered] = useState(false)
  const uploadRef = useRef<HTMLDivElement>(null)

  const documentsQuery = useQuery({
    queryKey: ['documents', activeProjectId, filter],
    queryFn: () =>
      listDocuments({
        projectId: activeProjectId,
        status: filter || undefined,
      }),
    enabled: !!activeProjectId,
  })

  const usageQuery = useQuery({
    queryKey: ['usage', activeProjectId],
    queryFn: () => getUsage(undefined, activeProjectId),
    enabled: !!activeProjectId,
  })

  const documents = useMemo<DocumentRow[]>(
    () => documentsQuery.data?.items ?? [],
    [documentsQuery.data],
  )
  const processingCount = documents.filter((d) => d.status === 'processing').length

  // Poll only while something is actually processing, and stop as soon as
  // nothing is -- a fixed interval would keep a quiet workspace awake forever.
  useEffect(() => {
    if (processingCount === 0) return
    const timer = window.setInterval(() => {
      void documentsQuery.refetch()
    }, 2000)
    return () => window.clearInterval(timer)
  }, [processingCount, documentsQuery])

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteDocument(id, activeProjectId),
    onSuccess: (_data, id) => {
      toast.success('Document deleted')
      setSelected((current) => {
        const next = new Set(current)
        next.delete(id)
        return next
      })
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (error) => toast.error('Not deleted', { description: problemMessage(error) }),
  })

  const sorted = useMemo(() => {
    const rows = [...documents]
    const factor = sort.direction === 'desc' ? -1 : 1
    rows.sort((a, b) => {
      const left = String(a[sort.key] ?? '')
      const right = String(b[sort.key] ?? '')
      return left.localeCompare(right) * factor
    })
    return rows
  }, [documents, sort])

  const toggleSort = (key: SortKey) =>
    setSort((current) =>
      current.key === key
        ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
        : { key, direction: 'asc' },
    )

  /*
   * The KPI row uses only what the API actually returns. `GET /usage` gives
   * pages, documents and AI cost for the month; the review and auto-accept
   * figures are counted from the documents in view, and the card says so rather
   * than implying a month-wide statistic it cannot produce. A
   * `GET /documents/stats` endpoint is in BACKEND_REQUESTS.md.
   */
  const needsReview = documents.filter((d) => d.status === 'needs_review').length
  const completed = documents.filter((d) => d.status === 'completed').length
  const decided = needsReview + completed
  const usage = usageQuery.data

  /*
   * The welcome screen replaces the dashboard rather than sitting above it, and
   * only while the account is genuinely empty: with a filter applied, an empty
   * list means "nothing matched", not "nothing here". It never comes back once
   * a document exists.
   */
  const firstVisit =
    !documentsQuery.isLoading &&
    !filter &&
    documents.length === 0 &&
    !welcomeDismissed

  const startUpload = () => {
    setWelcomeDismissed(true)
    // Let the upload zone mount before scrolling to it.
    window.requestAnimationFrame(() =>
      uploadRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' }),
    )
  }

  const endTour = () => {
    setTourOpen(false)
    setTourOffered(true)
    markTourSeen(user?.id)
  }

  const declineTour = () => {
    setTourOffered(true)
    markTourSeen(user?.id)
  }

  return (
    <Page
      title="Documents"
      description="Upload an invoice. Every value comes back with the words it was read from."
    >
      {tourOpen && <Tour onClose={endTour} />}

      {/*
        * The tour is never started for the user: it is offered. On an empty
        * account the welcome offers it; on an account that already has
        * documents but has never seen it, this one line does, and the
        * localStorage flag means it is not asked twice.
        */}
      {!firstVisit && !tourOffered && !hasSeenTour(user?.id) && !tourOpen && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-md)] border bg-[var(--surface-raised)] px-4 py-2.5">
          <p className="text-sm text-[var(--text-secondary)]">
            New here? A one-minute tour covers uploading, reviewing and using
            your data.
          </p>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="secondary" onClick={() => setTourOpen(true)}>
              Take the tour
            </Button>
            <Button size="sm" variant="ghost" onClick={declineTour}>
              No thanks
            </Button>
          </div>
        </div>
      )}

      {firstVisit && (
        <div className="mb-5">
          <Welcome
            onUpload={startUpload}
            onTour={() => {
              setWelcomeDismissed(true)
              setTourOpen(true)
            }}
          />
        </div>
      )}

      <div
        className={cn(
          'mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4',
          firstVisit && 'hidden',
        )}
      >
        <StatCard
          label="Documents this month"
          value={usage?.documents ?? 0}
          hint={`${usage?.pages ?? 0} pages`}
          icon={<FileText className="h-4 w-4" />}
          loading={usageQuery.isLoading}
        />
        <StatCard
          label="Needs review"
          value={needsReview}
          hint="In the list below"
          tone={needsReview > 0 ? 'warning' : 'default'}
          icon={<AlertTriangle className="h-4 w-4" />}
          loading={documentsQuery.isLoading}
        />
        <StatCard
          label="Accepted without review"
          value={decided ? formatPercent(completed / decided, 0) : '—'}
          hint={decided ? `${completed} of ${decided} decided` : 'No decisions yet'}
          icon={<CircleCheck className="h-4 w-4" />}
          loading={documentsQuery.isLoading}
        />
        <StatCard
          label="AI cost this month"
          value={formatCost(usage?.ai_cost_usd)}
          hint="Charged by the provider"
          icon={<Coins className="h-4 w-4" />}
          loading={usageQuery.isLoading}
        />
      </div>

      <div ref={uploadRef} data-tour="upload" className={cn('mb-5', firstVisit && 'hidden')}>
        <UploadZone
          projectId={activeProjectId}
          onUploaded={() => queryClient.invalidateQueries({ queryKey: ['documents'] })}
        />
      </div>

      <div className={cn('mb-3 flex items-center justify-between gap-3', firstVisit && 'hidden')}>
        <div
          role="tablist"
          aria-label="Filter by status"
          className="flex items-center gap-0.5 rounded-[var(--radius-md)] border bg-[var(--surface-raised)] p-0.5"
        >
          {FILTERS.map((option) => (
            <button
              key={option.value}
              role="tab"
              aria-selected={filter === option.value}
              onClick={() => setFilter(option.value)}
              className={cn(
                'rounded-[var(--radius-sm)] px-2.5 py-1 text-sm font-medium transition-colors duration-100',
                filter === option.value
                  ? 'bg-[var(--surface-selected)] text-[var(--text-brand)]'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
              )}
            >
              {option.label}
            </button>
          ))}
        </div>

        {selected.size > 0 && (
          <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
            <span className="tabular">{selected.size} selected</span>
            <Button size="sm" variant="secondary" onClick={() => setSelected(new Set())}>
              Clear
            </Button>
          </div>
        )}
      </div>

      <div className={cn(firstVisit && 'hidden')}>
      <TableShell>
        <Table>
          <THead>
            <TH width="36px">
              <input
                type="checkbox"
                aria-label="Select all"
                className="h-3.5 w-3.5 accent-[var(--accent-solid)]"
                checked={sorted.length > 0 && selected.size === sorted.length}
                onChange={(e) =>
                  setSelected(
                    e.target.checked ? new Set(sorted.map((d) => d.id)) : new Set(),
                  )
                }
              />
            </TH>
            <TH
              sortable
              direction={sort.key === 'filename' ? sort.direction : null}
              onSort={() => toggleSort('filename')}
            >
              Document
            </TH>
            <TH>Type</TH>
            <TH
              sortable
              direction={sort.key === 'status' ? sort.direction : null}
              onSort={() => toggleSort('status')}
            >
              Status
            </TH>
            <TH align="right">Pages</TH>
            <TH
              align="right"
              sortable
              direction={sort.key === 'created_at' ? sort.direction : null}
              onSort={() => toggleSort('created_at')}
            >
              Uploaded
            </TH>
            <TH width="56px" align="right">
              <span className="sr-only">Actions</span>
            </TH>
          </THead>

          {documentsQuery.isLoading ? (
            <TableSkeleton rows={5} columns={7} />
          ) : sorted.length === 0 ? (
            <TBody>
              <tr>
                <td colSpan={7}>
                  <EmptyState
                    icon={<Inbox className="h-5 w-5" />}
                    title={filter ? 'Nothing with that status' : 'No documents yet'}
                    description={
                      filter
                        ? 'Try a different filter.'
                        : 'Drop an invoice above and it will appear here as it processes.'
                    }
                  />
                </td>
              </tr>
            </TBody>
          ) : (
            <TBody>
              {sorted.map((doc) => (
                <TR key={doc.id} selected={selected.has(doc.id)}>
                  <TD>
                    <input
                      type="checkbox"
                      aria-label={`Select ${doc.filename}`}
                      className="h-3.5 w-3.5 accent-[var(--accent-solid)]"
                      checked={selected.has(doc.id)}
                      onChange={(e) =>
                        setSelected((current) => {
                          const next = new Set(current)
                          if (e.target.checked) next.add(doc.id)
                          else next.delete(doc.id)
                          return next
                        })
                      }
                    />
                  </TD>
                  <TD>
                    <Link
                      to={`/app/documents/${doc.id}`}
                      className="flex items-center gap-2 font-medium text-[var(--text-primary)] hover:text-[var(--text-brand)]"
                    >
                      <FileText className="h-4 w-4 shrink-0 text-[var(--text-tertiary)]" />
                      <span className="truncate">{doc.filename}</span>
                    </Link>
                  </TD>
                  <TD className="text-[var(--text-secondary)]">
                    {doc.document_type?.replace(/_/g, ' ') ?? '—'}
                  </TD>
                  <TD>
                    <StatusBadge status={doc.status} />
                  </TD>
                  <TD numeric className="text-[var(--text-secondary)]">
                    {doc.pages ?? '—'}
                  </TD>
                  <TD numeric title={doc.created_at ?? undefined} className="text-[var(--text-secondary)]">
                    {formatDate(doc.created_at)}
                  </TD>
                  <TD align="right">
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={`Delete ${doc.filename}`}
                      onClick={() => setPendingDelete(doc)}
                      className="text-[var(--text-tertiary)] hover:text-[var(--color-danger-600)]"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TD>
                </TR>
              ))}
            </TBody>
          )}
        </Table>
      </TableShell>
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        title={`Delete ${pendingDelete?.filename}?`}
        description="This removes the document and every extraction, correction and decision made on it. It cannot be undone."
        loading={deleteMutation.isPending}
        onConfirm={() => {
          if (pendingDelete) deleteMutation.mutate(pendingDelete.id)
          setPendingDelete(null)
        }}
      />
    </Page>
  )
}
