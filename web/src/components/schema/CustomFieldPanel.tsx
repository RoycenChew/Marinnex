import { useState } from 'react'
import { Plus, Trash2, Wand2 } from 'lucide-react'
import type { CustomFieldInput } from '../../api/types'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { HelpHint } from '../ui/VerificationBadge'

/**
 * Fields the template does not have.
 *
 * The honest framing matters here more than the form does. A template field has
 * been written, tested and given validators; a field someone types into this box
 * has a sentence of description and nothing else behind it. It is still grounded
 * — it has to be found on the page — but nothing checks that it means what the
 * customer thinks it means. The panel says so once, plainly, rather than
 * implying the two are equivalent.
 */

const KINDS: { value: CustomFieldInput['kind']; label: string; help: string }[] = [
  { value: 'text', label: 'Text', help: 'Words or a reference, like a job number.' },
  { value: 'number', label: 'Number', help: 'A quantity. Comes back as a string.' },
  {
    value: 'money',
    label: 'Amount',
    help: 'An amount of money, in the document’s own currency.',
  },
  { value: 'date', label: 'Date', help: 'Comes back as YYYY-MM-DD.' },
]

const MAX_FIELDS = 10
const MAX_HINTS = 5
const MAX_DESCRIPTION = 200

const BLANK: CustomFieldInput = {
  name: '',
  kind: 'text',
  description: '',
  hints: [],
  required: false,
}

export function CustomFieldPanel({
  fields,
  onChange,
  disabled,
}: {
  fields: CustomFieldInput[]
  onChange: (next: CustomFieldInput[]) => void
  disabled?: boolean
}) {
  const [draft, setDraft] = useState<CustomFieldInput>(BLANK)
  const [hint, setHint] = useState('')

  // The same rule the backend enforces, checked here so a user is told before
  // they submit rather than after.
  const nameOk = /^[a-z][a-z0-9_]{0,63}$/.test(draft.name)
  const taken = fields.some((f) => f.name === draft.name)
  const canAdd =
    !disabled &&
    nameOk &&
    !taken &&
    draft.description.trim().length > 0 &&
    fields.length < MAX_FIELDS

  const add = () => {
    if (!canAdd) return
    onChange([...fields, { ...draft, description: draft.description.trim() }])
    setDraft(BLANK)
    setHint('')
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-[var(--surface-sunken)] px-4 py-2">
        <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--text-secondary)]">
          Your own fields
          <HelpHint label="What is a custom field?">
            Something this template does not already read — a site reference, a
            project code. Describe it and we look for it on the page.
          </HelpHint>
        </span>
        <span className="tabular text-xs text-[var(--text-tertiary)]">
          {fields.length} of {MAX_FIELDS}
        </span>
      </div>

      {fields.length > 0 && (
        <ul className="divide-y">
          {fields.map((field) => (
            <li key={field.name} className="flex items-start gap-3 px-4 py-2.5">
              <div className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-1.5">
                  <code className="text-sm font-medium text-[var(--text-primary)]">
                    {field.name}
                  </code>
                  <Badge tone="brand">Custom</Badge>
                  <Badge tone="neutral">
                    {KINDS.find((k) => k.value === field.kind)?.label}
                  </Badge>
                  {field.required && <Badge tone="warning">Required</Badge>}
                </span>
                <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
                  {field.description}
                </p>
                {(field.hints?.length ?? 0) > 0 && (
                  <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                    Labelled: {field.hints?.join(' · ')}
                  </p>
                )}
              </div>
              <Button
                size="icon"
                variant="ghost"
                disabled={disabled}
                aria-label={`Remove ${field.name}`}
                onClick={() => onChange(fields.filter((f) => f.name !== field.name))}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </li>
          ))}
        </ul>
      )}

      {fields.length < MAX_FIELDS && (
        <div className="border-t px-4 py-3">
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-[var(--text-secondary)]">
                Name it the way your system will read it
              </span>
              <input
                value={draft.name}
                disabled={disabled}
                placeholder="site_ref"
                onChange={(e) =>
                  setDraft({ ...draft, name: e.target.value.toLowerCase() })
                }
                className="rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2.5 py-1.5 font-mono text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
              />
              <span className="text-xs text-[var(--text-tertiary)]">
                {draft.name && !nameOk
                  ? 'Lower case letters, numbers and underscores, starting with a letter.'
                  : taken
                    ? 'You already have a field with that name.'
                    : 'Lower case, no spaces — for example site_ref.'}
              </span>
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-[var(--text-secondary)]">
                What kind of value
              </span>
              <select
                value={draft.kind}
                disabled={disabled}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    kind: e.target.value as CustomFieldInput['kind'],
                  })
                }
                className="rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2.5 py-1.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
              >
                {KINDS.map((kind) => (
                  <option key={kind.value} value={kind.value}>
                    {kind.label}
                  </option>
                ))}
              </select>
              <span className="text-xs text-[var(--text-tertiary)]">
                {KINDS.find((k) => k.value === draft.kind)?.help}
              </span>
            </label>
          </div>

          <label className="mt-3 flex flex-col gap-1">
            <span className="text-xs font-medium text-[var(--text-secondary)]">
              Describe it as you would to a new colleague
            </span>
            <textarea
              value={draft.description}
              disabled={disabled}
              rows={2}
              maxLength={MAX_DESCRIPTION}
              placeholder="The site reference printed near the delivery address."
              onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              className="resize-none rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2.5 py-1.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
            />
            <span className="tabular text-xs text-[var(--text-tertiary)]">
              {draft.description.length} / {MAX_DESCRIPTION}
            </span>
          </label>

          <div className="mt-3">
            <span className="text-xs font-medium text-[var(--text-secondary)]">
              How is it labelled on the document? (optional)
            </span>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              {(draft.hints ?? []).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() =>
                    setDraft({
                      ...draft,
                      hints: (draft.hints ?? []).filter((h) => h !== value),
                    })
                  }
                  aria-label={`Remove label ${value}`}
                  className="rounded-[var(--radius-xs)] border px-1.5 py-0.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
                >
                  {value} ×
                </button>
              ))}
              {(draft.hints?.length ?? 0) < MAX_HINTS && (
                <input
                  value={hint}
                  disabled={disabled}
                  placeholder="D/O No"
                  aria-label="Add a label it may appear under"
                  onChange={(e) => setHint(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key !== 'Enter' || !hint.trim()) return
                    e.preventDefault()
                    setDraft({
                      ...draft,
                      hints: [...(draft.hints ?? []), hint.trim().slice(0, 40)],
                    })
                    setHint('')
                  }}
                  className="w-32 rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2 py-1 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
                />
              )}
            </div>
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">
              Press Enter after each one. Malay and English both help — "No.
              Pesanan" and "D/O No" are the same field on different invoices.
            </p>
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <label className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={draft.required}
                disabled={disabled}
                onChange={(e) => setDraft({ ...draft, required: e.target.checked })}
                className="h-3.5 w-3.5 accent-[var(--accent-solid)]"
              />
              A document without it needs review
            </label>
            <Button variant="secondary" disabled={!canAdd} onClick={add}>
              <Plus className="h-3.5 w-3.5" />
              Add field
            </Button>
          </div>
        </div>
      )}

      {/* Said once, where the decision is made. A custom field is grounded like
          any other, but nothing validates that it means what you think. */}
      <div className="flex items-start gap-2 border-t bg-[var(--surface-sunken)] px-4 py-2.5 text-xs text-[var(--text-secondary)]">
        <Wand2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--text-tertiary)]" />
        <p>
          Your fields are found on the page like any other — if we cannot point
          at the words, the document waits for a person. But nothing checks that
          the value means what you intended, the way subtotal and tax are checked
          against each other. Test on a few of your own documents and read the
          results before you rely on them.
        </p>
      </div>
    </div>
  )
}
