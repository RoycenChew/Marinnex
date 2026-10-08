import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { CommandPalette } from './CommandPalette'
import { useMediaQuery } from '../../lib/useMediaQuery'

const COLLAPSE_KEY = 'fdip.sidebar.collapsed'

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === '1'
    } catch {
      return false
    }
  })
  const [searchOpen, setSearchOpen] = useState(false)
  /* C10: a 240px sidebar in a 390px viewport leaves no room for the product, so
     below 768px it becomes a drawer over the content instead of a column beside
     it. The collapse preference above is a desktop concern and is left alone. */
  const narrow = useMediaQuery('(max-width: 768px)')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const location = useLocation()

  // Navigating is the end of the drawer's job.
  useEffect(() => setDrawerOpen(false), [location.pathname])

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0')
    } catch {
      // A layout preference is not worth failing a render over. Note this is a
      // *preference*, never data: rule 2.13 keeps extracted values out of
      // storage entirely.
    }
  }, [collapsed])

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--surface-page)]">
      {narrow ? (
        drawerOpen && (
          <>
            <div
              className="fixed inset-0 z-40 bg-[var(--color-slate-950)]/50"
              onClick={() => setDrawerOpen(false)}
            />
            <div className="fixed inset-y-0 left-0 z-50">
              <Sidebar collapsed={false} onToggle={() => setDrawerOpen(false)} />
            </div>
          </>
        )
      ) : (
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          onOpenSearch={() => setSearchOpen(true)}
          onOpenNav={narrow ? () => setDrawerOpen(true) : undefined}
        />
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
      <CommandPalette open={searchOpen} onOpenChange={setSearchOpen} />
    </div>
  )
}

/**
 * The standard page frame: a max width, consistent gutters, and a header whose
 * title, description and primary action always sit in the same place. Screens
 * that need the full viewport (the review split view) opt out by not using it.
 */
export function Page({
  title,
  description,
  action,
  children,
}: {
  title: string
  description?: string
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div className="mx-auto w-full max-w-[var(--spacing-content-max)] px-6 py-6">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
            {title}
          </h1>
          {description && (
            <p className="mt-1 text-sm text-[var(--text-secondary)]">{description}</p>
          )}
        </div>
        {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
      </div>
      {children}
    </div>
  )
}
