import { useEffect, useState } from 'react'
import { Command } from 'cmdk'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  Activity,
  BookOpen,
  FileText,
  KeyRound,
  Moon,
  Sun,
  Table2,
  Upload,
} from 'lucide-react'
import { listDocuments } from '../../api/queries'
import { useAuth } from '../../context/AuthContext'
import { statusMeta } from '../../lib/status'
import { useTheme } from '../../lib/theme'

/** Below this, a query matches too much to be useful. */
const MIN_QUERY = 2

/** The server caps `limit` at 200, so that is the most this can ever see. */
const SEARCH_WINDOW = 200

/**
 * ⌘K: navigation, and finding a document by name.
 *
 * The search is **client side over the most recent documents**, because the API
 * still has no search endpoint — `docs/BACKEND_REQUESTS.md` §5. That is a real
 * limitation, not a hidden one: if the project holds more than the window below,
 * the palette says so rather than quietly returning nothing for a document the
 * user knows exists. A search that fails silently is worse than one that admits
 * its range.
 *
 * Nothing else in the app is touched. The list is fetched only while the
 * palette is open, through the same `listDocuments` every screen already uses,
 * so closing it costs nothing and no other screen's behaviour changes.
 */
export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const { resolved, toggle } = useTheme()
  const { activeProjectId } = useAuth()
  const [search, setSearch] = useState('')

  /* Fetched only while the palette is open, and kept for a minute so reopening
     it does not re-request. One query, one endpoint the app already uses. */
  const documentsQuery = useQuery({
    queryKey: ['palette-documents', activeProjectId],
    queryFn: () => listDocuments({ projectId: activeProjectId, limit: SEARCH_WINDOW }),
    enabled: open && !!activeProjectId,
    staleTime: 60_000,
  })

  const term = search.trim().toLowerCase()
  const documents = documentsQuery.data?.items ?? []
  const matches =
    term.length >= MIN_QUERY
      ? documents.filter((entry) =>
          (entry.filename ?? '').toLowerCase().includes(term),
        )
      : []

  /* The window is full and the server says there is more, so a document the
     user is looking for may simply be older than anything searched. */
  const beyondWindow =
    !!documentsQuery.data?.next_cursor && documents.length >= SEARCH_WINDOW

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'k' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        onOpenChange(!open)
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onOpenChange])

  const go = (path: string) => {
    navigate(path)
    setSearch('')
    onOpenChange(false)
  }

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Command menu"
      className="fixed inset-0 z-50"
      overlayClassName="fixed inset-0 bg-[var(--color-slate-950)]/40 backdrop-blur-[2px]"
      contentClassName="fixed top-[20%] left-1/2 w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 overflow-hidden rounded-[var(--radius-lg)] border bg-[var(--surface-overlay)] shadow-lg"
    >
      <Command.Input
        value={search}
        onValueChange={setSearch}
        placeholder="Search documents, or go to…"
        className="w-full border-b bg-transparent px-4 py-3 text-base text-[var(--text-primary)] outline-none placeholder:text-[var(--text-tertiary)]"
      />
      <Command.List className="max-h-80 overflow-y-auto p-2">
        <Command.Empty className="px-2 py-6 text-center text-sm text-[var(--text-secondary)]">
          {documentsQuery.isLoading
            ? 'Looking…'
            : term.length >= MIN_QUERY
              ? 'No document or page matches that.'
              : 'Nothing matches that.'}
        </Command.Empty>

        {/* Documents first: when someone types a name, that is what they want,
            not a page whose label happens to contain the same letters. */}
        {matches.length > 0 && (
          <Group heading="Documents">
            {matches.slice(0, 8).map((entry) => (
              <Item
                key={entry.id}
                value={entry.filename ?? entry.id}
                onSelect={() => go(`/app/documents/${entry.id}`)}
                icon={<FileText className="h-4 w-4" />}
              >
                <span className="flex min-w-0 flex-1 items-center justify-between gap-3">
                  <span className="truncate">{entry.filename}</span>
                  <span className="shrink-0 text-xs text-[var(--text-tertiary)]">
                    {statusMeta(entry.status).label}
                  </span>
                </span>
              </Item>
            ))}
          </Group>
        )}

        {term.length >= MIN_QUERY && beyondWindow && (
          <p className="px-3 py-1.5 text-xs text-[var(--text-tertiary)]">
            Searching the {SEARCH_WINDOW} most recent documents. Older ones are
            on the Documents page.
          </p>
        )}

        <Group heading="Go to">
          <Item onSelect={() => go('/app')} icon={<FileText className="h-4 w-4" />}>
            Documents
          </Item>
          <Item onSelect={() => go('/app/schemas')} icon={<Table2 className="h-4 w-4" />}>
            Schemas
          </Item>
          <Item onSelect={() => go('/app/api-keys')} icon={<KeyRound className="h-4 w-4" />}>
            API keys
          </Item>
          <Item
            onSelect={() => go('/app/usage')}
            icon={<Activity className="h-4 w-4" />}
          >
            Usage
          </Item>
          <Item onSelect={() => go('/guide')} icon={<BookOpen className="h-4 w-4" />}>
            Guide and help
          </Item>
        </Group>

        <Group heading="Actions">
          <Item
            onSelect={() => {
              go('/app')
              // The upload input lives on the Documents page; opening it from
              // here would need a ref across routes, so this navigates and lets
              // the user drop a file.
            }}
            icon={<Upload className="h-4 w-4" />}
          >
            Upload a document
          </Item>
          <Item
            onSelect={() => {
              toggle()
              onOpenChange(false)
            }}
            icon={
              resolved === 'dark' ? (
                <Sun className="h-4 w-4" />
              ) : (
                <Moon className="h-4 w-4" />
              )
            }
          >
            Switch to {resolved === 'dark' ? 'light' : 'dark'} theme
          </Item>
        </Group>
      </Command.List>
    </Command.Dialog>
  )
}

function Group({
  heading,
  children,
}: {
  heading: string
  children: React.ReactNode
}) {
  return (
    <Command.Group
      heading={heading}
      className="mb-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:text-[var(--text-tertiary)]"
    >
      {children}
    </Command.Group>
  )
}

function Item({
  children,
  onSelect,
  icon,
  value,
}: {
  children: React.ReactNode
  onSelect: () => void
  icon: React.ReactNode
  /* cmdk derives a value from the rendered text when this is absent. A
     document item renders its status beside the name, so it is given the
     filename explicitly — otherwise the status word joins the haystack and
     typing "ready" would match every finished document. */
  value?: string
}) {
  return (
    <Command.Item
      value={value}
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-2.5 rounded-[var(--radius-sm)] px-2 py-2 text-sm text-[var(--text-primary)] data-[selected=true]:bg-[var(--surface-hover)]"
    >
      <span className="text-[var(--text-tertiary)]">{icon}</span>
      {children}
    </Command.Item>
  )
}
