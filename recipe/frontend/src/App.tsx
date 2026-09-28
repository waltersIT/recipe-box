import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { BrowserRouter, Link, NavLink, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import AuthProvider from './components/AuthProvider'
import Avatar from './components/Avatar'
import AuthPage from './pages/AuthPage'
import CapturePage from './pages/CapturePage'
import EditorPage from './pages/EditorPage'
import HomePage from './pages/HomePage'
import ImportPage from './pages/ImportPage'
import ProfilePage from './pages/ProfilePage'
import RecipePage from './pages/RecipePage'

function AccountMenu() {
  const { user, loading, signOut } = useAuth()
  const [open, setOpen] = useState(false)
  const { pathname, search } = useLocation()

  if (loading) return null
  if (!user) {
    return (
      <Link to={`/login?next=${encodeURIComponent(pathname + search)}`} className="button small">
        Sign in
      </Link>
    )
  }
  return (
    <div className="account-menu">
      <button type="button" className="account-button" aria-expanded={open} onClick={() => setOpen((on) => !on)}>
        <Avatar user={user.profile} size={30} />
        <span className="truncate">{user.profile.name}</span>
      </button>
      {open && (
        <>
          <button type="button" className="menu-backdrop" aria-label="Close menu" onClick={() => setOpen(false)} />
          {/* Any choice in here navigates or signs out, so the menu closes. */}
          <div className="menu" onClick={() => setOpen(false)}>
            <Link to={`/u/${user.username}`}>Your profile</Link>
            <Link to="/?mine=1">Your recipes</Link>
            <Link to="/?liked=1">Recipes you like</Link>
            <button type="button" onClick={() => void signOut()}>
              Sign out
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function Shell() {
  const { pathname } = useLocation()
  const { user } = useAuth()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">
          <svg viewBox="0 0 32 32" width="26" height="26" aria-hidden="true">
            <rect width="32" height="32" rx="8" fill="currentColor" />
            <path d="M9 11h14M9 16h14M9 21h9" stroke="var(--bg)" strokeWidth="2.5" strokeLinecap="round" />
          </svg>
          Recipe Box
        </Link>
        <nav>
          <NavLink to="/" end className="nav-home">
            Recipes
          </NavLink>
          {user && <NavLink to="/recipes/new">New</NavLink>}
          <NavLink to="/import" className="button primary small">
            Import
          </NavLink>
          <AccountMenu />
        </nav>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  )
}

/** Uploading needs an account, so these pages send you to sign in first. */
function RequireAccount({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const { pathname, search } = useLocation()
  if (loading) return <p className="muted">Loading…</p>
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(pathname + search)}`} replace />
  return <>{children}</>
}

// Remount the editor when moving between /recipes/new and /recipes/new?import=1.
function EditorRoute() {
  const location = useLocation()
  return (
    <RequireAccount>
      <EditorPage key={location.pathname + location.search} />
    </RequireAccount>
  )
}

function NotFound() {
  return (
    <div className="empty">
      <h2>Page not found</h2>
      <Link to="/" className="button">
        Back to recipes
      </Link>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<HomePage />} />
            <Route path="login" element={<AuthPage mode="login" />} />
            <Route path="signup" element={<AuthPage mode="signup" />} />
            <Route path="u/:username" element={<ProfilePage />} />
            <Route
              path="import"
              element={
                <RequireAccount>
                  <ImportPage />
                </RequireAccount>
              }
            />
            <Route path="capture" element={<CapturePage />} />
            <Route path="recipes/new" element={<EditorRoute />} />
            <Route path="recipes/:id" element={<RecipePage />} />
            <Route path="recipes/:id/edit" element={<EditorRoute />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
