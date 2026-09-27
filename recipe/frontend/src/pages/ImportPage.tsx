import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import Bookmarklet from '../components/Bookmarklet'
import FileDrop from '../components/FileDrop'
import { setPendingImport } from '../importStore'
import { objectUrl } from '../lib/objectUrl'
import type { ImportConfig, ImportResult } from '../types'

function isPdf(file: File) {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
}

function FileThumb({ file, onRemove }: { file: File; onRemove: () => void }) {
  const url = isPdf(file) ? '' : objectUrl(file)
  return (
    <li className="file-thumb">
      {url ? <img src={url} alt="" /> : <span className="file-icon">PDF</span>}
      <span className="truncate small">{file.name}</span>
      <button type="button" className="icon-button" aria-label={`Remove ${file.name}`} onClick={onRemove}>
        ×
      </button>
    </li>
  )
}

export default function ImportPage() {
  const navigate = useNavigate()
  const [config, setConfig] = useState<ImportConfig | null>(null)
  const [url, setUrl] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState<'url' | 'files' | null>(null)
  const [urlError, setUrlError] = useState('')
  const [fileError, setFileError] = useState('')

  useEffect(() => {
    api.importConfig().then(setConfig).catch(() => setConfig(null))
  }, [])

  function addFiles(incoming: File[]) {
    setFileError('')
    const usable = incoming.filter((f) => isPdf(f) || f.type.startsWith('image/') || /\.(heic|heif)$/i.test(f.name))
    if (usable.length < incoming.length) setFileError('Only PDFs and images can be imported.')
    setFiles((prev) => [...prev, ...usable].slice(0, config?.max_files ?? 10))
  }

  // Paste a screenshot straight from the clipboard.
  useEffect(() => {
    function onPaste(event: ClipboardEvent) {
      const target = event.target as HTMLElement | null
      if (target?.tagName === 'INPUT' || target?.tagName === 'TEXTAREA') return
      const pasted = Array.from(event.clipboardData?.files ?? [])
      if (!pasted.length) return
      event.preventDefault()
      const stamp = new Date().toISOString().slice(11, 19).replace(/:/g, '')
      addFiles(
        pasted.map((file, i) =>
          file.name && file.name !== 'image.png' ? file : new File([file], `Pasted ${stamp}-${i + 1}.png`, { type: file.type }),
        ),
      )
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  })

  function openInEditor(result: ImportResult, sourceFiles: File[]) {
    setPendingImport({ result, files: sourceFiles })
    navigate('/recipes/new?import=1')
  }

  async function importUrl(event: FormEvent) {
    event.preventDefault()
    if (!url.trim()) return
    setBusy('url')
    setUrlError('')
    try {
      openInEditor(await api.importUrl(url.trim()), [])
    } catch (err) {
      setUrlError((err as Error).message)
      setBusy(null)
    }
  }

  async function importFiles() {
    setBusy('files')
    setFileError('')
    try {
      openInEditor(await api.importFiles(files), files)
    } catch (err) {
      setFileError((err as Error).message)
      setBusy(null)
    }
  }

  return (
    <div className="import-page">
      <h1>Import a recipe</h1>

      <section className="panel">
        <h2>From a link</h2>
        <p className="muted">Paste a link to a recipe page. Most recipe sites work.</p>
        <form className="url-form" onSubmit={importUrl}>
          <input
            // Plain text rather than type="url" so links without https:// are accepted.
            type="text"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            placeholder="https://www.example.com/best-banana-bread"
            aria-label="Recipe link"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={busy !== null}
          />
          <button type="submit" className="button primary" disabled={busy !== null || !url.trim()}>
            {busy === 'url' ? 'Reading page…' : 'Import'}
          </button>
        </form>
        {urlError && <div className="alert error">{urlError}</div>}
      </section>

      <section className="panel">
        <h2>From a PDF, screenshot or photo</h2>
        <p className="muted">
          Add several screenshots of the same recipe (in order) and they'll be combined.
          {config && (
            <>
              {' '}
              {config.llm_enabled
                ? `Claude (${config.llm_model}) reads them.`
                : config.ocr_engine
                  ? `Text is recognized on this computer (${config.ocr_engine}).`
                  : 'Text PDFs work; screenshots need Tesseract or a Claude API key.'}
            </>
          )}
        </p>
        <FileDrop onFiles={addFiles} disabled={busy !== null} />
        {files.length > 0 && (
          <>
            <ul className="file-list">
              {files.map((file, index) => (
                <FileThumb
                  key={`${file.name}-${index}`}
                  file={file}
                  onRemove={() => setFiles((prev) => prev.filter((_, i) => i !== index))}
                />
              ))}
            </ul>
            <div className="button-row">
              <button type="button" className="button primary" onClick={importFiles} disabled={busy !== null}>
                {busy === 'files'
                  ? config?.llm_enabled
                    ? 'Claude is reading… (can take ~30s)'
                    : 'Reading…'
                  : `Import ${files.length} file${files.length === 1 ? '' : 's'}`}
              </button>
              <button type="button" className="button" onClick={() => setFiles([])} disabled={busy !== null}>
                Clear
              </button>
            </div>
          </>
        )}
        {fileError && <div className="alert error">{fileError}</div>}
      </section>

      <section className="panel">
        <h2>From your browser</h2>
        <p className="muted">
          Some big sites block imports from links. Drag this button to your bookmarks bar, then click it while you're
          on a recipe page. The page is read in your browser tab.
        </p>
        <Bookmarklet />
      </section>
    </div>
  )
}
