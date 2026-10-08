import { useEffect } from 'react'
import { Command } from 'cmdk'
import { useNavigate } from 'react-router-dom'
import {
  Activity,
  FileText,
  KeyRound,
  Moon,
  Sun,
  Table2,
  Upload,
} from 'lucide-react'
import { useTheme } from '../../lib/theme'

/**
 * ⌘K navigation.
 *
 * Deliberately not a document search: the API has no search endpoint, and a
 * palette that silently fails to find a document the user knows exists is worse
 * than one that only claims to navigate. Document search is in
 * BACKEND_REQUESTS.md.
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
        placeholder="Go to…"
        className="w-full border-b bg-transparent px-4 py-3 text-base text-[var(--text-primary)] outline-none placeholder:text-[var(--text-tertiary)]"
      />
      <Command.List className="max-h-80 overflow-y-auto p-2">
        <Command.Empty className="px-2 py-6 text-center text-sm text-[var(--text-secondary)]">
          Nothing matches that.
        </Command.Empty>

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
}: {
  children: React.ReactNode
  onSelect: () => void
  icon: React.ReactNode
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-2.5 rounded-[var(--radius-sm)] px-2 py-2 text-sm text-[var(--text-primary)] data-[selected=true]:bg-[var(--surface-hover)]"
    >
      <span className="text-[var(--text-tertiary)]">{icon}</span>
      {children}
    </Command.Item>
  )
}
