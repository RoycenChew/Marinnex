import { NavLink } from 'react-router-dom'
import {
  Activity,
  ChevronsLeft,
  FileText,
  KeyRound,
  PanelLeft,
  Table2,
} from 'lucide-react'
import { Logo } from '../Logo'
import { cn } from '../../lib/utils'

/**
 * Grouped navigation.
 *
 * The groups are the audience, not the feature list: a finance reviewer lives in
 * Workspace and never opens Developers, while an integrator does the reverse.
 * Grouping by who needs it means neither has to read past the other's tools.
 */
const GROUPS: {
  label: string
  items: { to: string; icon: typeof FileText; label: string; end?: boolean }[]
}[] = [
  {
    label: 'Workspace',
    items: [
      { to: '/app', icon: FileText, label: 'Documents', end: true },
      { to: '/app/usage', icon: Activity, label: 'Usage' },
    ],
  },
  {
    label: 'Developers',
    items: [
      { to: '/app/schemas', icon: Table2, label: 'Schemas' },
      { to: '/app/api-keys', icon: KeyRound, label: 'API keys' },
    ],
  },
]

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean
  onToggle: () => void
}) {
  return (
    <aside
      className={cn(
        'z-30 flex shrink-0 flex-col border-r bg-[var(--surface-raised)]',
        'transition-[width] duration-150 ease-out',
        collapsed ? 'w-14' : 'w-60',
      )}
    >
      <div
        className={cn(
          'flex h-14 items-center border-b',
          collapsed ? 'justify-center px-0' : 'justify-between px-4',
        )}
      >
        {collapsed ? (
          <Wordmark compact />
        ) : (
          <>
            <Wordmark />
            <button
              type="button"
              onClick={onToggle}
              aria-label="Collapse sidebar"
              className="rounded-[var(--radius-sm)] p-1 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
            >
              <ChevronsLeft className="h-4 w-4" />
            </button>
          </>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {GROUPS.map((group) => (
          <div key={group.label} className="mb-4 last:mb-0">
            {!collapsed && (
              <div className="px-2 pb-1.5 text-xs font-medium text-[var(--text-tertiary)]">
                {group.label}
              </div>
            )}
            <ul className="flex flex-col gap-0.5">
              {group.items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    title={collapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2.5 rounded-[var(--radius-sm)] px-2 py-1.5',
                        'text-sm font-medium transition-colors duration-100',
                        collapsed && 'justify-center px-0',
                        isActive
                          ? 'bg-[var(--surface-selected)] text-[var(--text-brand)]'
                          : 'text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]',
                      )
                    }
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      {collapsed && (
        <div className="border-t p-2">
          <button
            type="button"
            onClick={onToggle}
            aria-label="Expand sidebar"
            className="flex w-full items-center justify-center rounded-[var(--radius-sm)] p-1.5 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
          >
            <PanelLeft className="h-4 w-4" />
          </button>
        </div>
      )}
    </aside>
  )
}

function Wordmark({ compact }: { compact?: boolean }) {
  // The wordmark is a 505x227 lockup, so at a 24px cap height the name is
  // unreadable. Expanded it gets 36px; collapsed, the mark carries it alone.
  return compact ? (
    <Logo variant="mark" className="h-7" />
  ) : (
    <Logo variant="full" className="h-9" />
  )
}
