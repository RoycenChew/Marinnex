import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Eye, EyeOff } from 'lucide-react'
import { apiClient } from '../api/client'
import { getHealth } from '../api/queries'
import { useAuth } from '../context/AuthContext'
import { problemMessage } from '../lib/status'
import { AuthShell, Field } from '../components/AuthShell'
import { Button } from '../components/ui/Button'

export default function Login() {
  /* Default to open: if health cannot be reached, hiding the only route to an
     account would be the worse failure. */
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, retry: false })
  const openRegistration = health.data?.allow_registration !== false

  /* The seeded development account, pre-filled so a local run is one click.
     `import.meta.env.DEV` is false in any built bundle, so a deployed site
     starts empty — shipping a known credential in the page source would be
     handing it to everyone who opens the sign-in form. */
  const [email, setEmail] = useState(import.meta.env.DEV ? 'dev@fdip.local' : '')
  const [password, setPassword] = useState(import.meta.env.DEV ? 'devpass' : '')
  const [reveal, setReveal] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { checkAuth } = useAuth()
  const navigate = useNavigate()

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const { error: apiError } = await apiClient.POST('/v1/auth/login', {
        body: { email, password },
      })
      if (apiError) {
        setError(problemMessage(apiError))
        return
      }
      await checkAuth()
      navigate('/app')
    } catch (caught) {
      setError(problemMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Sign in"
      subtitle="Evidence-backed extraction for financial documents."
      footer={
        openRegistration ? (
          <>
            No account yet?{' '}
            <Link
              to="/register"
              className="font-medium text-[var(--text-brand)] hover:underline"
            >
              Create one
            </Link>
          </>
        ) : (
          /* Said plainly rather than by omission: someone who expected to sign
             up should learn why they cannot, not wonder where the link went. */
          <>Invite only. Ask the team for an invitation.</>
        )
      }
      error={error}
    >
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Field label="Email">
          <input
            type="email"
            required
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2.5 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
          />
        </Field>
        <Field label="Password">
          <div className="relative">
            <input
              type={reveal ? 'text' : 'password'}
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] py-2 pr-9 pl-2.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
            />
            <button
              type="button"
              onClick={() => setReveal((r) => !r)}
              aria-label={reveal ? 'Hide password' : 'Show password'}
              className="absolute top-1/2 right-2 -translate-y-1/2 rounded-[var(--radius-xs)] p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
            >
              {reveal ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </button>
          </div>
        </Field>
        <Button type="submit" variant="primary" size="lg" loading={busy} className="mt-1 w-full">
          {busy ? 'Signing in' : 'Sign in'}
        </Button>
      </form>
    </AuthShell>
  )
}
