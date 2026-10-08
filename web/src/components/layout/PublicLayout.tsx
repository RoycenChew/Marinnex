import { Link, NavLink, Outlet } from 'react-router-dom'
import { Moon, Sun } from 'lucide-react'
import { Logo } from '../Logo'
import { BRAND } from '../../lib/copy'
import { useAuth } from '../../context/AuthContext'
import { useTheme } from '../../lib/theme'
import { cn } from '../../lib/utils'

/**
 * The frame for the public site.
 *
 * Deliberately separate from `AppLayout`: no sidebar, no project switcher, and
 * **no authenticated request**. `useAuth` is read only to decide whether the
 * header says "Sign in" or "Go to app" — the provider has already resolved by
 * the time this renders, and nothing here fetches.
 */

const NAV = [
  { to: '/guide', label: 'Guide' },
  { to: '/trust', label: 'Trust' },
]

export default function PublicLayout() {
  const { user } = useAuth()
  const { resolved, toggle } = useTheme()

  return (
    <div className="flex min-h-screen flex-col bg-[var(--surface-page)]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-[var(--radius-sm)] focus:bg-[var(--surface-overlay)] focus:px-3 focus:py-2 focus:text-sm"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-40 border-b bg-[var(--surface-raised)]/90 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between gap-4 px-5">
          <Link to="/" className="flex items-center" aria-label={BRAND.name}>
            <Logo className="h-6" />
          </Link>

          <nav aria-label="Main" className="flex items-center gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'rounded-[var(--radius-sm)] px-2.5 py-1.5 text-sm font-medium transition-colors',
                    isActive
                      ? 'text-[var(--text-brand)]'
                      : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
            <button
              type="button"
              onClick={toggle}
              aria-label={resolved === 'dark' ? 'Use light theme' : 'Use dark theme'}
              className="ml-1 rounded-[var(--radius-sm)] p-2 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
            >
              {resolved === 'dark' ? (
                <Moon className="h-4 w-4" />
              ) : (
                <Sun className="h-4 w-4" />
              )}
            </button>
            <Link
              to={user ? '/app' : '/login'}
              className="ml-2 inline-flex h-8 items-center rounded-[var(--radius-sm)] bg-[var(--accent-solid)] px-3 text-sm font-medium text-white hover:bg-[var(--accent-solid-hover)]"
            >
              {user ? 'Go to app' : 'Sign in'}
            </Link>
          </nav>
        </div>
      </header>

      <main id="main" className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t bg-[var(--surface-raised)]">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-5 py-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <Logo variant="mark" className="h-5" />
            <span className="text-sm text-[var(--text-secondary)]">
              {BRAND.name}
            </span>
          </div>
          {/* C5: the disclosure belongs where every page can see it. */}
          <p className="max-w-md text-xs text-[var(--text-tertiary)]">
            AI processing is performed by DeepSeek (servers in China).{' '}
            <Link to="/trust" className="underline hover:text-[var(--text-secondary)]">
              How we handle your documents
            </Link>
          </p>
        </div>
      </footer>
    </div>
  )
}
