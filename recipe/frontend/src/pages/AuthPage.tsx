import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth'

/** Sign in and sign up, which differ by little more than a heading. */
export default function AuthPage({ mode }: { mode: 'login' | 'signup' }) {
  const { user, loading, signIn, signUp } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = params.get('next') || '/'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (loading) return <p className="muted">Loading…</p>
  if (user) return <Navigate to={next} replace />

  const isSignUp = mode === 'signup'

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (isSignUp) await signUp({ username: username.trim(), password, display_name: displayName.trim() })
      else await signIn(username.trim(), password)
      navigate(next, { replace: true })
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="panel">
        <h1>{isSignUp ? 'Create an account' : 'Sign in'}</h1>
        <p className="muted">
          {isSignUp
            ? 'You need an account to add recipes. Reading them is open to everyone.'
            : 'Welcome back.'}
        </p>
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              value={username}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
              onChange={(e) => setUsername(e.target.value)}
            />
            {isSignUp && <span className="hint">Letters, numbers, and . _ - only. This is your profile address.</span>}
          </div>
          {isSignUp && (
            <div className="field">
              <label htmlFor="display_name">Display name</label>
              <input
                id="display_name"
                value={displayName}
                autoComplete="nickname"
                placeholder="Optional"
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </div>
          )}
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              autoComplete={isSignUp ? 'new-password' : 'current-password'}
              required
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && <div className="alert error">{error}</div>}
          <div className="button-row">
            <button type="submit" className="button primary" disabled={busy}>
              {busy ? 'Just a moment…' : isSignUp ? 'Create account' : 'Sign in'}
            </button>
          </div>
        </form>
        <p className="muted small">
          {isSignUp ? (
            <>
              Already have an account? <Link to={`/login?next=${encodeURIComponent(next)}`}>Sign in</Link>
            </>
          ) : (
            <>
              New here? <Link to={`/signup?next=${encodeURIComponent(next)}`}>Create an account</Link>
            </>
          )}
        </p>
      </div>
    </div>
  )
}
