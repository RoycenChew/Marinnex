import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import {
  Check,
  ChevronDown,
  LogOut,
  Monitor,
  Moon,
  Search,
  Sun,
  User,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useTheme, type ThemeChoice } from '../../lib/theme'
import { cn } from '../../lib/utils'

const MENU_CONTENT =
  'z-50 min-w-48 overflow-hidden rounded-[var(--radius-md)] border ' +
  'bg-[var(--surface-overlay)] p-1 shadow-lg ' +
  'data-[state=open]:animate-in data-[state=open]:fade-in-0'

const MENU_ITEM =
  'flex cursor-pointer items-center gap-2 rounded-[var(--radius-sm)] px-2 py-1.5 ' +
  'text-sm text-[var(--text-primary)] outline-none ' +
  'data-[highlighted]:bg-[var(--surface-hover)]'

export function TopBar({ onOpenSearch }: { onOpenSearch: () => void }) {
  const { user, projects, activeProjectId, setActiveProjectId, logout } = useAuth()
  const { choice, resolved, setChoice } = useTheme()
  const activeProject = projects.find((p) => p.id === activeProjectId)

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b bg-[var(--surface-raised)] px-4">
      <div className="flex min-w-0 items-center gap-2">
        {/* Project switcher. Rendered as a menu rather than a native <select>
            so it can show a check against the active project and stay on-theme
            in dark mode, which a native control cannot. */}
        <DropdownMenu.Root>
          <DropdownMenu.Trigger
            className={cn(
              'flex items-center gap-1.5 rounded-[var(--radius-sm)] px-2 py-1.5',
              'text-sm font-medium text-[var(--text-primary)]',
              'hover:bg-[var(--surface-hover)] data-[state=open]:bg-[var(--surface-hover)]',
            )}
          >
            <span className="truncate">{activeProject?.name ?? 'Select project'}</span>
            <ChevronDown className="h-3.5 w-3.5 text-[var(--text-tertiary)]" />
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content align="start" sideOffset={6} className={MENU_CONTENT}>
              <DropdownMenu.Label className="px-2 py-1.5 text-xs text-[var(--text-tertiary)]">
                Projects
              </DropdownMenu.Label>
              {projects.map((project) => (
                <DropdownMenu.Item
                  key={project.id}
                  onSelect={() => setActiveProjectId(project.id)}
                  className={MENU_ITEM}
                >
                  <Check
                    className={cn(
                      'h-3.5 w-3.5',
                      project.id === activeProjectId
                        ? 'text-[var(--text-brand)]'
                        : 'opacity-0',
                    )}
                  />
                  {project.name}
                </DropdownMenu.Item>
              ))}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>

      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={onOpenSearch}
          className={cn(
            'flex items-center gap-2 rounded-[var(--radius-sm)] border px-2.5 py-1.5',
            'text-sm text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)]',
            'min-w-56 justify-between',
          )}
        >
          <span className="flex items-center gap-2">
            <Search className="h-3.5 w-3.5" />
            Search
          </span>
          <kbd className="rounded-[var(--radius-xs)] border px-1.5 py-0.5 font-sans text-2xs text-[var(--text-tertiary)]">
            ⌘K
          </kbd>
        </button>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger
            aria-label="Theme"
            className="rounded-[var(--radius-sm)] p-2 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
          >
            {resolved === 'dark' ? (
              <Moon className="h-4 w-4" />
            ) : (
              <Sun className="h-4 w-4" />
            )}
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content align="end" sideOffset={6} className={MENU_CONTENT}>
              {(
                [
                  ['light', 'Light', Sun],
                  ['dark', 'Dark', Moon],
                  ['system', 'System', Monitor],
                ] as [ThemeChoice, string, typeof Sun][]
              ).map(([value, label, Icon]) => (
                <DropdownMenu.Item
                  key={value}
                  onSelect={() => setChoice(value)}
                  className={MENU_ITEM}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {label}
                  {choice === value && (
                    <Check className="ml-auto h-3.5 w-3.5 text-[var(--text-brand)]" />
                  )}
                </DropdownMenu.Item>
              ))}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger
            className="flex items-center gap-2 rounded-[var(--radius-sm)] py-1 pr-1.5 pl-1 hover:bg-[var(--surface-hover)]"
            aria-label="Account"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--accent-subtle)] text-xs font-semibold text-[var(--text-brand)]">
              {(user?.email ?? '?').charAt(0).toUpperCase()}
            </span>
            <ChevronDown className="h-3.5 w-3.5 text-[var(--text-tertiary)]" />
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content align="end" sideOffset={6} className={MENU_CONTENT}>
              <div className="flex items-center gap-2 px-2 py-2">
                <User className="h-4 w-4 text-[var(--text-tertiary)]" />
                <span className="truncate text-sm text-[var(--text-primary)]">
                  {user?.email}
                </span>
              </div>
              <DropdownMenu.Separator className="my-1 h-px bg-[var(--border-subtle)]" />
              <DropdownMenu.Item onSelect={() => logout()} className={MENU_ITEM}>
                <LogOut className="h-3.5 w-3.5" />
                Sign out
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </header>
  )
}
