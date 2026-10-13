import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertTriangle, Check, Eye, EyeOff, KeyRound } from 'lucide-react'
import { toast } from 'sonner'
import { changePassword, listActivity } from '../api/queries'
import { useAuth } from '../context/AuthContext'
import { Page } from '../components/layout/AppLayout'
import { Button } from '../components/ui/Button'
import { Card, CardHeader } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Table'
import { formatDateTime } from '../lib/format'
import { problemMessage } from '../lib/status'

/**
 * Your account: change your password, and see what has happened on the project.
 *
 * Both of these existed only on the server before. A password change meant
 * asking the owner to run a command, and the audit trail had been recorded
 * since the first commit with no way out of the database.
 *
 * The warning below is the part that matters most. There is **no
 * forgotten-password email**, so the honest thing is to say so where someone
 * is choosing a password, not to leave them to discover it when locked out.
 */

const MIN_PASSWORD = 8

/** Plain words for the audit vocabulary. Anything unlisted falls back to the
 *  raw action, which is better than inventing a friendly name for it. */
const ACTIONS: Record<string, string> = {
  uploaded: 'Uploaded a document',
  extracted: 'Read a document',
  corrected: 'Corrected a value',
  approved: 'Approved an extraction',
  rejected: 'Rejected an extraction',
  deleted: 'Deleted a document',
  exported: 'Exported data',
  job_failed: 'A document could not be processed',
  extract_requested: 'Extraction requested through the API',
  schema_created: 'Created a schema',
  schema_version_created: 'Added a schema version',
  schema_version_updated: 'Edited a draft schema version',
  schema_archived: 'Archived a schema',
  schema_restored: 'Restored a schema',
  schema_deleted: 'Deleted a schema',
  schema_test_run: 'Ran a schema test',
  key_created: 'Created an API key',
  key_revoked: 'Revoked an API key',
  field_checked: 'Marked a field as checked',
  field_unchecked: 'Unmarked a field',
  password_changed: 'Changed a password',
  // The decision route records `payload.action + "d"`, so "reject" becomes
  // "rejectd". Mapped rather than corrected: the string is already in stored
  // audit rows, and renaming it would orphan every one of them.
  rejectd: 'Rejected an extraction',
}

export default function Profile() {
  const { user, activeProjectId } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [reveal, setReveal] = useState(false)

  const activityQuery = useQuery({
    queryKey: ['activity', activeProjectId],
    queryFn: () => listActivity(activeProjectId),
    enabled: !!activeProjectId,
  })

  const passwordMutation = useMutation({
    mutationFn: () =>
      changePassword({ current_password: current, new_password: next }),
    onSuccess: () => {
      toast.success('Password changed')
      setCurrent('')
      setNext('')
      setConfirm('')
    },
    onError: (error) =>
      toast.error('Not changed', { description: problemMessage(error) }),
  })

  const tooShort = next.length > 0 && next.length < MIN_PASSWORD
  const mismatch = confirm.length > 0 && confirm !== next
  const canSubmit =
    current.length > 0 && next.length >= MIN_PASSWORD && confirm === next

  return (
    <Page
      title="Your account"
      description={user?.email ?? 'Signed in'}
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <Card padded={false}>
            <div className="border-b px-4 py-3">
              <CardHeader
                title="Change your password"
                description="Takes effect immediately. You stay signed in here."
              />
            </div>

            {/* Said before the form, not after it. Someone who reads this while
                choosing a password can act on it; someone who reads it after
                being locked out cannot. */}
            <div className="flex items-start gap-2.5 border-b bg-[var(--color-warning-50)] px-4 py-3 text-sm text-[var(--color-warning-700)] dark:bg-[var(--color-warning-500)]/10 dark:text-[var(--color-warning-400)]">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                <strong>Remember this password.</strong> There is no reset email
                and no "forgot password" link. If you lose it you cannot sign in,
                and getting back in means asking us to reset it by hand. Keep it
                in a password manager.
              </p>
            </div>

            <form
              className="flex flex-col gap-3 px-4 py-4"
              onSubmit={(event) => {
                event.preventDefault()
                if (canSubmit) passwordMutation.mutate()
              }}
            >
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-[var(--text-secondary)]">
                  Current password
                </span>
                <input
                  type="password"
                  autoComplete="current-password"
                  value={current}
                  onChange={(e) => setCurrent(e.target.value)}
                  className="rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2.5 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-[var(--text-secondary)]">
                  New password
                </span>
                <div className="relative">
                  <input
                    type={reveal ? 'text' : 'password'}
                    autoComplete="new-password"
                    value={next}
                    onChange={(e) => setNext(e.target.value)}
                    aria-describedby="new-password-hint"
                    className="w-full rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] py-2 pr-9 pl-2.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
                  />
                  <button
                    type="button"
                    onClick={() => setReveal((value) => !value)}
                    aria-label={reveal ? 'Hide password' : 'Show password'}
                    className="absolute top-1/2 right-2 -translate-y-1/2 rounded-[var(--radius-xs)] p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                  >
                    {reveal ? (
                      <EyeOff className="h-3.5 w-3.5" />
                    ) : (
                      <Eye className="h-3.5 w-3.5" />
                    )}
                  </button>
                </div>
                <span
                  id="new-password-hint"
                  className={
                    'text-xs ' +
                    (tooShort
                      ? 'text-[var(--color-danger-600)]'
                      : 'text-[var(--text-tertiary)]')
                  }
                >
                  At least {MIN_PASSWORD} characters.
                </span>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-[var(--text-secondary)]">
                  Confirm new password
                </span>
                <input
                  type={reveal ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className="rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2.5 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
                />
                {/* Caught here rather than by the server, because a typo in a
                    field you cannot read is the likeliest way to lock yourself
                    out of a product with no reset email. */}
                {mismatch && (
                  <span className="text-xs text-[var(--color-danger-600)]">
                    These do not match.
                  </span>
                )}
              </label>

              <Button
                type="submit"
                variant="primary"
                disabled={!canSubmit}
                loading={passwordMutation.isPending}
                className="mt-1 self-start"
              >
                <KeyRound className="h-3.5 w-3.5" />
                Change password
              </Button>
            </form>
          </Card>
        </div>

        <Card padded={false}>
          <div className="border-b px-4 py-3">
            <CardHeader
              title="Account activity"
              description="What has happened on this project, newest first."
            />
          </div>

          {activityQuery.isLoading ? (
            <div className="flex flex-col gap-2 p-4">
              {[0, 1, 2, 3].map((row) => (
                <Skeleton key={row} className="h-8 w-full" />
              ))}
            </div>
          ) : (activityQuery.data?.items ?? []).length === 0 ? (
            <p className="px-4 py-6 text-sm text-[var(--text-tertiary)]">
              Nothing yet. Uploads, corrections, approvals, exports and key
              changes appear here.
            </p>
          ) : (
            <ul className="divide-y">
              {(activityQuery.data?.items ?? []).map((event) => (
                <li
                  key={event.id}
                  className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 px-4 py-2.5"
                >
                  <span className="text-sm text-[var(--text-primary)]">
                    {ACTIONS[event.action] ?? event.action.replace(/_/g, ' ')}
                  </span>
                  <span
                    className="tabular shrink-0 text-xs text-[var(--text-tertiary)]"
                    title={event.created_at ?? undefined}
                  >
                    {formatDateTime(event.created_at)}
                  </span>
                  <span className="w-full truncate font-mono text-xs text-[var(--text-tertiary)]">
                    {event.object_type} {event.object_id}
                  </span>
                </li>
              ))}
            </ul>
          )}

          {/* The list is what was recorded, not everything that happened. Say
              which, so nobody reads it as a complete security log. */}
          <p className="border-t px-4 py-2.5 text-xs text-[var(--text-tertiary)]">
            <Check className="mr-1 inline h-3 w-3" />
            Records the actions above. It never stores what a document said —
            only which document, and which field.
          </p>
        </Card>
      </div>
    </Page>
  )
}
