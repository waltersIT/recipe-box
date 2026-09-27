import { useEffect } from 'react'
import { BrowserRouter, Link, NavLink, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import CapturePage from './pages/CapturePage'
import EditorPage from './pages/EditorPage'
import ImportPage from './pages/ImportPage'
import LibraryPage from './pages/LibraryPage'
import RecipePage from './pages/RecipePage'

function Shell() {
  const { pathname } = useLocation()
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
          <NavLink to="/recipes/new">New</NavLink>
          <NavLink to="/import" className="button primary small">
            Import
          </NavLink>
        </nav>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  )
}

// Remount the editor when moving between /recipes/new and /recipes/new?import=1.
function EditorRoute() {
  const location = useLocation()
  return <EditorPage key={location.pathname + location.search} />
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
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<LibraryPage />} />
          <Route path="import" element={<ImportPage />} />
          <Route path="capture" element={<CapturePage />} />
          <Route path="recipes/new" element={<EditorRoute />} />
          <Route path="recipes/:id" element={<RecipePage />} />
          <Route path="recipes/:id/edit" element={<EditorRoute />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
