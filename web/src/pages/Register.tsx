import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import { getHealth } from '../api/queries'
import { useAuth } from '../context/AuthContext'
import { problemMessage } from '../lib/status'
import { AuthShell, Field } from '../components/AuthShell'
import { Button } from '../components/ui/Button'

const MIN_PASSWORD = 8

export default function Register() {
  // Someone who follows an old link should be told here, not after filling the
  // form in and being refused.
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, retry: false })
  const openRegistration = health.data?.allow_registration !== false

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [reveal, setReveal] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { checkAuth } = useAuth()
  const navigate = useNavigate()

  const tooShort = password.length > 0 && password.length < MIN_PASSWORD

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const { error: apiError } = await apiClient.POST('/v1/auth/register', {
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
      title="Create an account"
      subtitle="A project is created for you, ready to receive documents."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-[var(--text-brand)] hover:underline">
            Sign in
          </Link>
        </>
      }
      error={error}
    >
      {!openRegistration && (
        <p className="mb-4 rounded-[var(--radius-md)] border bg-[var(--surface-sunken)] p-3 text-sm text-[var(--text-secondary)]">
          New accounts are invite only at the moment. Ask the team for an
          invitation and you will be sent a sign-in.
        </p>
      )}
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
              minLength={MIN_PASSWORD}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-describedby="password-hint"
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
          {/* Stated up front rather than only after a rejected submit. */}
          <span
            id="password-hint"
            className={
              'text-xs ' +
              (tooShort ? 'text-[var(--color-danger-600)]' : 'text-[var(--text-tertiary)]')
            }
          >
            At least {MIN_PASSWORD} characters.
          </span>
        </Field>
        <Button
          type="submit"
          variant="primary"
          size="lg"
          loading={busy}
          disabled={tooShort || !openRegistration}
          className="mt-1 w-full"
        >
          {busy ? 'Creating account' : 'Create account'}
        </Button>
      </form>
    </AuthShell>
  )
}
