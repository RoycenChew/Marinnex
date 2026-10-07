import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from '../../lib/utils'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline'
type Size = 'sm' | 'md' | 'lg' | 'icon'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
}

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-[var(--accent-solid)] text-white hover:bg-[var(--accent-solid-hover)] ' +
    'shadow-xs disabled:bg-[var(--color-slate-300)] dark:disabled:bg-[var(--color-slate-700)]',
  secondary:
    'bg-[var(--surface-raised)] text-[var(--text-primary)] border border-[var(--border-strong)] ' +
    'hover:bg-[var(--surface-hover)] shadow-xs',
  outline:
    'bg-transparent text-[var(--text-secondary)] border border-[var(--border-subtle)] ' +
    'hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]',
  ghost:
    'bg-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] ' +
    'hover:text-[var(--text-primary)]',
  danger:
    'bg-[var(--color-danger-600)] text-white hover:bg-[var(--color-danger-700)] shadow-xs',
}

const SIZES: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-xs gap-1.5',
  md: 'h-8 px-3 text-sm gap-2',
  lg: 'h-10 px-4 text-base gap-2',
  icon: 'h-8 w-8 p-0',
}

/**
 * The only button in the app.
 *
 * `loading` keeps the label in place and swaps the leading icon for a spinner,
 * rather than replacing the text with "Loading…" — a button that changes width
 * mid-click moves the thing the user is still pointing at.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'secondary', size = 'md', loading, children, disabled, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center rounded-[var(--radius-sm)] font-medium',
        'transition-colors duration-150 whitespace-nowrap select-none',
        'disabled:cursor-not-allowed disabled:opacity-60',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    >
      {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
      {children}
    </button>
  ),
)
Button.displayName = 'Button'
