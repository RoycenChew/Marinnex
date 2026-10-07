import type { ReactNode } from 'react'
import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react'
import { cn } from '../../lib/utils'

/**
 * The data table.
 *
 * Three decisions worth stating, because they are what make a dense table
 * readable rather than merely compact:
 *
 * - The header is sticky. A finance user scrolls a hundred rows and still needs
 *   to know which column is which.
 * - Numeric columns are right-aligned and tabular. A column of amounts that is
 *   left-aligned with proportional digits cannot be scanned at all.
 * - Row separators are a single hairline, not a border on every cell. Grid lines
 *   add structure the data does not have.
 */

export function TableShell({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'overflow-hidden rounded-[var(--radius-lg)] border bg-[var(--surface-raised)] shadow-xs',
        className,
      )}
    >
      {children}
    </div>
  )
}

export function Table({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className="overflow-x-auto">
      <table className={cn('w-full border-collapse text-sm', className)}>
        {children}
      </table>
    </div>
  )
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead className="sticky top-0 z-10 bg-[var(--surface-sunken)]">
      <tr className="border-b">{children}</tr>
    </thead>
  )
}

export type SortDirection = 'asc' | 'desc' | null

export function TH({
  children,
  align = 'left',
  sortable,
  direction = null,
  onSort,
  className,
  width,
}: {
  children: ReactNode
  align?: 'left' | 'right' | 'center'
  sortable?: boolean
  direction?: SortDirection
  onSort?: () => void
  className?: string
  width?: string
}) {
  const content = (
    <span
      className={cn(
        'inline-flex items-center gap-1',
        align === 'right' && 'flex-row-reverse',
      )}
    >
      {children}
      {sortable && (
        <span className="text-[var(--text-tertiary)]">
          {direction === 'asc' ? (
            <ArrowUp className="h-3 w-3" />
          ) : direction === 'desc' ? (
            <ArrowDown className="h-3 w-3" />
          ) : (
            <ChevronsUpDown className="h-3 w-3 opacity-40" />
          )}
        </span>
      )}
    </span>
  )

  return (
    <th
      scope="col"
      style={width ? { width } : undefined}
      aria-sort={
        direction === 'asc'
          ? 'ascending'
          : direction === 'desc'
            ? 'descending'
            : sortable
              ? 'none'
              : undefined
      }
      className={cn(
        'px-3 py-2 text-xs font-medium text-[var(--text-secondary)] whitespace-nowrap',
        align === 'right' && 'text-right',
        align === 'center' && 'text-center',
        align === 'left' && 'text-left',
        className,
      )}
    >
      {sortable ? (
        <button
          type="button"
          onClick={onSort}
          className="rounded-[var(--radius-xs)] hover:text-[var(--text-primary)]"
        >
          {content}
        </button>
      ) : (
        content
      )}
    </th>
  )
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y">{children}</tbody>
}

export function TR({
  children,
  onClick,
  selected,
  className,
}: {
  children: ReactNode
  onClick?: () => void
  selected?: boolean
  className?: string
}) {
  return (
    <tr
      onClick={onClick}
      className={cn(
        'transition-colors duration-100',
        onClick && 'cursor-pointer',
        selected
          ? 'bg-[var(--surface-selected)]'
          : 'hover:bg-[var(--surface-hover)]',
        className,
      )}
    >
      {children}
    </tr>
  )
}

export function TD({
  children,
  align = 'left',
  numeric,
  className,
  colSpan,
  title,
}: {
  children: ReactNode
  align?: 'left' | 'right' | 'center'
  numeric?: boolean
  className?: string
  colSpan?: number
  title?: string
}) {
  return (
    <td
      colSpan={colSpan}
      title={title}
      className={cn(
        'px-3 py-2.5 text-[var(--text-primary)] align-middle',
        numeric && 'tabular text-right',
        !numeric && align === 'right' && 'text-right',
        align === 'center' && 'text-center',
        className,
      )}
    >
      {children}
    </td>
  )
}

/** Rectangles in the shape of the content, not a spinner (UI spec section 4). */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-[var(--radius-xs)] bg-[var(--surface-sunken)]',
        className,
      )}
    />
  )
}

export function TableSkeleton({ rows = 5, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <TBody>
      {Array.from({ length: rows }).map((_, row) => (
        <tr key={row} className="border-b last:border-0">
          {Array.from({ length: columns }).map((__, column) => (
            <td key={column} className="px-3 py-2.5">
              <Skeleton
                className={cn('h-4', column === 0 ? 'w-40' : 'w-20')}
                // Slight stagger so the block reads as loading rather than as a
                // static placeholder graphic.
              />
            </td>
          ))}
        </tr>
      ))}
    </TBody>
  )
}

/**
 * An empty list is an invitation to act, so it carries the action rather than
 * only stating the absence.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      {icon && (
        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[var(--surface-sunken)] text-[var(--text-tertiary)]">
          {icon}
        </div>
      )}
      <p className="text-base font-medium text-[var(--text-primary)]">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-[var(--text-secondary)]">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
