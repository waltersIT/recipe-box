import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import SourcePreview from '../components/SourcePreview'
import StarRating from '../components/StarRating'
import TagInput from '../components/TagInput'
import { clearPendingImport, getPendingImport } from '../importStore'
import type { PendingImport } from '../importStore'
import { formatMinutes, hostname, linesToText, textToLines } from '../lib/format'
import { objectUrl } from '../lib/objectUrl'
import type { Recipe, RecipeFields, RecipeInput } from '../types'

interface Form {
  title: string
  description: string
  ingredients: string
  instructions: string
  notes: string
  servings: string
  prep_time: string
  cook_time: string
  total_time: string
  source_url: string
  source_name: string
  author: string
  tags: string[]
  rating: number
}

const EMPTY: Form = {
  title: '', description: '', ingredients: '', instructions: '', notes: '', servings: '',
  prep_time: '', cook_time: '', total_time: '', source_url: '', source_name: '', author: '',
  tags: [], rating: 0,
}

function toForm(recipe: Partial<RecipeFields> & { rating?: number }): Form {
  const minutes = (value: number | null | undefined) => (value ? String(value) : '')
  return {
    title: recipe.title ?? '',
    description: recipe.description ?? '',
    ingredients: linesToText(recipe.ingredients ?? []),
    instructions: linesToText(recipe.instructions ?? []),
    notes: recipe.notes ?? '',
    servings: recipe.servings ?? '',
    prep_time: minutes(recipe.prep_time),
    cook_time: minutes(recipe.cook_time),
    total_time: minutes(recipe.total_time),
    source_url: recipe.source_url ?? '',
    source_name: recipe.source_name ?? '',
    author: recipe.author ?? '',
    tags: recipe.tags ?? [],
    rating: recipe.rating ?? 0,
  }
}

function toPayload(form: Form): RecipeInput {
  const minutes = (value: string) => {
    const number = parseInt(value, 10)
    return Number.isFinite(number) && number > 0 ? number : null
  }
  return {
    title: form.title.trim(),
    description: form.description.trim(),
    ingredients: textToLines(form.ingredients),
    instructions: textToLines(form.instructions),
    notes: form.notes.trim(),
    servings: form.servings.trim(),
    prep_time: minutes(form.prep_time),
    cook_time: minutes(form.cook_time),
    total_time: minutes(form.total_time),
    source_url: form.source_url.trim(),
    source_name: form.source_name.trim(),
    author: form.author.trim(),
    tags: form.tags,
    rating: form.rating,
  }
}

const PARSER_LABELS: Record<string, string> = {
  'schema.org': "Read from the recipe data the site publishes, so it's usually exact.",
  claude: 'Read by Claude. Give it a quick check before saving.',
  text: 'Read by the built-in parser. Check it against the original before saving.',
}

export default function EditorPage() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const isEdit = Boolean(id)

  const [pending] = useState<PendingImport | null>(() =>
    !isEdit && searchParams.get('import') === '1' ? getPendingImport() : null,
  )
  const [original, setOriginal] = useState<Recipe | null>(null)
  const [form, setForm] = useState<Form>(() => (pending ? toForm(pending.result.draft) : EMPTY))
  const [loaded, setLoaded] = useState(!isEdit)
  const [dirty, setDirty] = useState(Boolean(pending))
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imageUrl, setImageUrl] = useState(pending?.result.draft.image_url ?? '')
  const [removeImage, setRemoveImage] = useState(false)
  const [tagSuggestions, setTagSuggestions] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const imageInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.tags().then((tags) => setTagSuggestions(tags.map((t) => t.name))).catch(() => {})
  }, [])

  useEffect(() => {
    if (!isEdit) return
    let cancelled = false
    api
      .getRecipe(id!)
      .then((recipe) => {
        if (cancelled) return
        setOriginal(recipe)
        setForm(toForm(recipe))
        setLoaded(true)
      })
      .catch((err: Error) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [id, isEdit])

  // Warn before closing the tab with unsaved changes.
  useEffect(() => {
    if (!dirty) return
    const handler = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [dirty])

  const localPreview = imageFile ? objectUrl(imageFile) : ''
  const shownImage = localPreview || (removeImage ? '' : imageUrl || original?.image || '')

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
    setDirty(true)
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!form.title.trim()) {
      setError('Give the recipe a title.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const payload = toPayload(form)
      let saved: Recipe
      if (isEdit) {
        saved = await api.updateRecipe(id!, payload)
      } else {
        payload.import_method = pending?.result.method ?? 'manual'
        if (imageUrl && !imageFile && !removeImage) payload.image_url = imageUrl
        saved = await api.createRecipe(payload)
      }
      if (imageFile) await api.uploadImage(saved.id, imageFile)
      else if (isEdit && removeImage && original?.image) await api.deleteImage(saved.id)
      if (!isEdit && pending?.files.length) await api.uploadAttachments(saved.id, pending.files)
      clearPendingImport()
      setDirty(false)
      navigate(`/recipes/${saved.id}`, { replace: true })
    } catch (err) {
      setError((err as Error).message)
      setSaving(false)
    }
  }

  if (!loaded) return error ? <div className="alert error">{error}</div> : <p className="muted">Loading…</p>

  const files = pending?.files ?? []
  const result = pending?.result

  return (
    <div className={`editor${files.length ? ' with-source' : ''}`}>
      <form className="editor-form" onSubmit={save}>
        <div className="editor-head">
          <h1>{isEdit ? 'Edit recipe' : pending ? 'Review import' : 'New recipe'}</h1>
          <div className="button-row">
            <Link to={isEdit ? `/recipes/${id}` : pending ? '/import' : '/'} className="button">
              Cancel
            </Link>
            <button type="submit" className="button primary" disabled={saving}>
              {saving ? 'Saving…' : 'Save recipe'}
            </button>
          </div>
        </div>

        {result && (
          <div className="alert info">
            <p>
              {PARSER_LABELS[result.parser]}
              {result.draft.source_url && (
                <>
                  {' '}
                  <a href={result.draft.source_url} target="_blank" rel="noreferrer">
                    Open the original page ↗
                  </a>
                </>
              )}
            </p>
            {result.warnings.length > 0 && (
              <ul>
                {result.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        {error && <div className="alert error">{error}</div>}

        <div className="field">
          <label htmlFor="title">Title</label>
          <input id="title" className="title-input" value={form.title} onChange={(e) => set('title', e.target.value)} required />
        </div>

        <div className="image-field">
          <div className="image-preview">
            {shownImage ? <img src={shownImage} alt="" /> : <span className="muted small">No photo</span>}
          </div>
          <div className="button-row">
            <input
              ref={imageInput}
              type="file"
              accept="image/*"
              hidden
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) {
                  setImageFile(file)
                  setRemoveImage(false)
                  setDirty(true)
                }
                e.target.value = ''
              }}
            />
            <button type="button" className="button small" onClick={() => imageInput.current?.click()}>
              {shownImage ? 'Replace photo' : 'Add photo'}
            </button>
            {shownImage && (
              <button
                type="button"
                className="button small danger-text"
                onClick={() => {
                  setImageFile(null)
                  setImageUrl('')
                  setRemoveImage(true)
                  setDirty(true)
                }}
              >
                Remove
              </button>
            )}
          </div>
        </div>

        <div className="field">
          <label htmlFor="description">Description</label>
          <textarea id="description" rows={2} value={form.description} onChange={(e) => set('description', e.target.value)} />
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="servings">Servings</label>
            <input id="servings" value={form.servings} placeholder="4 servings" onChange={(e) => set('servings', e.target.value)} />
          </div>
          {(['prep_time', 'cook_time', 'total_time'] as const).map((key) => (
            <div className="field" key={key}>
              <label htmlFor={key}>{key === 'prep_time' ? 'Prep' : key === 'cook_time' ? 'Cook' : 'Total'} (min)</label>
              <input
                id={key}
                type="number"
                min={0}
                inputMode="numeric"
                value={form[key]}
                onChange={(e) => set(key, e.target.value)}
              />
              <span className="hint">{Number(form[key]) >= 60 ? formatMinutes(Number(form[key])) : ''}</span>
            </div>
          ))}
        </div>

        <div className="field">
          <label htmlFor="ingredients">Ingredients</label>
          <textarea
            id="ingredients"
            rows={Math.min(Math.max(form.ingredients.split('\n').length + 1, 6), 24)}
            value={form.ingredients}
            onChange={(e) => set('ingredients', e.target.value)}
            placeholder={'2 cups flour\n1 tsp salt\n# For the glaze\n1 cup powdered sugar'}
          />
          <span className="hint">One ingredient per line. Start a line with # to make a section heading.</span>
        </div>

        <div className="field">
          <label htmlFor="instructions">Instructions</label>
          <textarea
            id="instructions"
            rows={Math.min(Math.max(form.instructions.split('\n').length * 2, 6), 30)}
            value={form.instructions}
            onChange={(e) => set('instructions', e.target.value)}
            placeholder={'Preheat the oven to 350°F.\nWhisk the dry ingredients together.'}
          />
          <span className="hint">One step per line. Start a line with # to make a section heading.</span>
        </div>

        <div className="field">
          <label htmlFor="notes">Notes</label>
          <textarea id="notes" rows={3} value={form.notes} onChange={(e) => set('notes', e.target.value)} />
        </div>

        <div className="field">
          <label htmlFor="tags">Tags</label>
          <TagInput value={form.tags} onChange={(tags) => set('tags', tags)} suggestions={tagSuggestions} />
        </div>

        <div className="field-row">
          <div className="field grow">
            <label htmlFor="source_url">Source link</label>
            <input id="source_url" type="url" value={form.source_url} onChange={(e) => set('source_url', e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="source_name">Source name</label>
            <input
              id="source_name"
              value={form.source_name}
              placeholder={form.source_url ? hostname(form.source_url) : 'Cookbook, website…'}
              onChange={(e) => set('source_name', e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="author">Author</label>
            <input id="author" value={form.author} onChange={(e) => set('author', e.target.value)} />
          </div>
        </div>

        <div className="field-row align-center">
          <div className="field">
            <span className="label">Your rating</span>
            <StarRating value={form.rating} onChange={(rating) => set('rating', rating)} />
            <span className="hint">Shown on the recipe. Only you can change it.</span>
          </div>
        </div>

        <div className="editor-foot button-row">
          <button type="submit" className="button primary" disabled={saving}>
            {saving ? 'Saving…' : 'Save recipe'}
          </button>
        </div>
      </form>

      {files.length > 0 && (
        <aside className="editor-source" aria-label="Original files">
          <h2 className="small-caps">Original</h2>
          <SourcePreview files={files} />
        </aside>
      )}
    </div>
  )
}
