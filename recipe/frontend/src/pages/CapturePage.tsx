import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { setPendingImport } from '../importStore'

interface CaptureMessage {
  type: 'recipebox-capture'
  url: string
  html: string
}

function isCapture(data: unknown): data is CaptureMessage {
  const message = data as CaptureMessage | null
  return (
    !!message &&
    message.type === 'recipebox-capture' &&
    typeof message.url === 'string' &&
    typeof message.html === 'string'
  )
}

/** Opened by the bookmarklet, which posts the recipe page's HTML here. */
export default function CapturePage() {
  const navigate = useNavigate()
  const { user, loading } = useAuth()
  const [status, setStatus] = useState<'waiting' | 'importing' | 'error'>(() => (window.opener ? 'waiting' : 'error'))
  const [message, setMessage] = useState(() =>
    window.opener ? '' : 'Open this page with the “Save to Recipe Box” bookmark while viewing a recipe.',
  )
  const handled = useRef(false)

  useEffect(() => {
    async function onMessage(event: MessageEvent) {
      // Only accept the page that opened this window.
      if (!window.opener || event.source !== window.opener || !isCapture(event.data) || handled.current) return
      handled.current = true
      setStatus('importing')
      try {
        const result = await api.importHtml(event.data.url, event.data.html)
        setPendingImport({ result, files: [] })
        navigate('/recipes/new?import=1', { replace: true })
      } catch (err) {
        setStatus('error')
        setMessage((err as Error).message)
      }
    }
    if (!window.opener) return
    window.addEventListener('message', onMessage)
    window.opener.postMessage('recipebox-ready', '*')
    const timeout = setTimeout(() => {
      if (!handled.current) {
        setStatus('error')
        setMessage("Didn't receive the page. Some sites block this; try saving the page as a PDF instead.")
      }
    }, 10000)
    return () => {
      window.removeEventListener('message', onMessage)
      clearTimeout(timeout)
    }
  }, [navigate])

  // Saving a page needs an account, and the bookmarklet opened this window
  // directly, so there's nothing to come back to after signing in.
  if (!loading && !user) {
    return (
      <div className="capture">
        <div className="alert info">Sign in to save this recipe, then click the bookmark again.</div>
        <Link to="/login?next=/import" className="button primary">
          Sign in
        </Link>
      </div>
    )
  }

  return (
    <div className="capture">
      {status === 'error' ? (
        <>
          <div className="alert error">{message}</div>
          <Link to="/import" className="button">
            Other ways to import
          </Link>
        </>
      ) : (
        <p className="muted">{status === 'waiting' ? 'Waiting for the recipe page…' : 'Reading the recipe…'}</p>
      )}
    </div>
  )
}
