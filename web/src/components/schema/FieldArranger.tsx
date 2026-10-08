import { useState } from 'react'
import { ChevronDown, ChevronUp, GripVertical } from 'lucide-react'
import type { FieldConfigInput } from '../../api/types'
import { HelpHint } from '../ui/VerificationBadge'
import { cn } from '../../lib/utils'

/**
 * The selected fields, in the order they will arrive, with their output names.
 *
 * Three things a customer asks for the moment they integrate: call it what my
 * system calls it, put it where my system expects it, and tell me which ones
 * have to be there. None of it changes extraction — it is how the result is
 * presented.
 *
 * Dragging is the obvious gesture and it is not the only one: the same move is
 * on two buttons, because a keyboard user cannot drag and a pointer is not the
 * only way to use a form. The drag handle is decorative for assistive tech;
 * the buttons carry the accessible names.
 */

export type ArrangedField = {
  path: string
  label: string
  /** The template's own default, shown when the user has not overridden it. */
  requiredDefault: boolean
}

export function FieldArranger({
  fields,
  config,
  onChange,
  disabled,
}: {
  fields: ArrangedField[]
  config: Record<string, FieldConfigInput>
  onChange: (next: Record<string, FieldConfigInput>) => void
  disabled?: boolean
}) {
  const [dragging, setDragging] = useState<string | null>(null)

  const set = (path: string, patch: Partial<FieldConfigInput>) => {
    const current = config[path] ?? {}
    const merged = { ...current, ...patch }
    // Drop keys that are back to their default, so an untouched field stores
    // nothing and the stored config stays readable.
    const cleaned = Object.fromEntries(
      Object.entries(merged).filter(([, value]) => value !== null && value !== ''),
    )
    onChange({ ...config, [path]: cleaned })
  }

  /** Reordering writes an explicit `order` on every row, so the result does not
   *  depend on where the template happened to put things. */
  const reorder = (from: number, to: number) => {
    if (to < 0 || to >= fields.length || from === to) return
    const paths = fields.map((f) => f.path)
    const [moved] = paths.splice(from, 1)
    paths.splice(to, 0, moved)
    const next = { ...config }
    paths.forEach((path, index) => {
      next[path] = { ...(next[path] ?? {}), order: index }
    })
    onChange(next)
  }

  if (fields.length === 0) {
    return (
      <p className="px-4 py-6 text-sm text-[var(--text-tertiary)]">
        Pick some fields above and they will appear here, in the order your
        system will receive them.
      </p>
    )
  }

  return (
    <ul className="divide-y">
      {fields.map((field, index) => {
        const entry = config[field.path] ?? {}
        const required = entry.required ?? field.requiredDefault
        return (
          <li
            key={field.path}
            draggable={!disabled}
            onDragStart={() => setDragging(field.path)}
            onDragEnd={() => setDragging(null)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={() => {
              if (!dragging) return
              reorder(fields.findIndex((f) => f.path === dragging), index)
              setDragging(null)
            }}
            className={cn(
              'flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5',
              dragging === field.path && 'opacity-50',
            )}
          >
            <GripVertical
              aria-hidden
              className="h-3.5 w-3.5 shrink-0 cursor-grab text-[var(--text-tertiary)]"
            />
            <span className="tabular w-5 shrink-0 text-xs text-[var(--text-tertiary)]">
              {index + 1}
            </span>

            <span className="min-w-0 flex-1 truncate text-sm text-[var(--text-primary)]">
              {field.label}
            </span>

            <label className="flex items-center gap-1.5">
              <span className="sr-only">Output name for {field.label}</span>
              <input
                value={entry.alias ?? ''}
                disabled={disabled}
                placeholder={field.path}
                onChange={(e) =>
                  set(field.path, { alias: e.target.value.trim() || null })
                }
                className="w-44 rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2 py-1 font-mono text-xs text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)] disabled:opacity-60"
              />
            </label>

            <label className="flex shrink-0 items-center gap-1.5 text-xs text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={required}
                disabled={disabled}
                onChange={(e) => set(field.path, { required: e.target.checked })}
                className="h-3.5 w-3.5 accent-[var(--accent-solid)]"
              />
              Required
            </label>

            <span className="flex shrink-0 items-center gap-0.5">
              <button
                type="button"
                aria-label={`Move ${field.label} up`}
                disabled={disabled || index === 0}
                onClick={() => reorder(index, index - 1)}
                className="rounded-[var(--radius-xs)] p-1 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)] disabled:opacity-30"
              >
                <ChevronUp className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                aria-label={`Move ${field.label} down`}
                disabled={disabled || index === fields.length - 1}
                onClick={() => reorder(index, index + 1)}
                className="rounded-[var(--radius-xs)] p-1 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)] disabled:opacity-30"
              >
                <ChevronDown className="h-3.5 w-3.5" />
              </button>
            </span>
          </li>
        )
      })}
    </ul>
  )
}

export function ArrangerHeader() {
  return (
    <div className="flex items-center justify-between gap-2 border-b bg-[var(--surface-sunken)] px-4 py-2">
      <span className="text-xs font-medium text-[var(--text-secondary)]">
        Order and output names
      </span>
      <span className="flex items-center gap-1 text-xs text-[var(--text-tertiary)]">
        Leave a name blank to keep the default
        <HelpHint label="What is an output name?">
          The key your software reads this value under. Renaming it here changes
          what the API sends you — it does not change what is read from the
          document.
        </HelpHint>
      </span>
    </div>
  )
}
