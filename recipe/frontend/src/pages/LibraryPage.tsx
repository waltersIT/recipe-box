import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import RecipeCard from '../components/RecipeCard'
import type { RecipeSummary, TagCount } from '../types'

const SORTS = [
  { value: 'newest', label: 'Newest' },
  { value: 'title', label: 'A–Z' },
  { value: 'rating', label: 'Top rated' },
  { value: 'updated', label: 'Recently edited' },
]

export default function LibraryPage() {
  const [params, setParams] = useSearchParams()
  const search = params.get('q') ?? ''
  const tag = params.get('tag') ?? ''
  const favorites = params.get('fav') === '1'
  const sort = params.get('sort') ?? 'newest'

  const [query, setQuery] = useState(search)
  const [recipes, setRecipes] = useState<RecipeSummary[] | null>(null)
  const [tags, setTags] = useState<TagCount[]>([])
  const [error, setError] = useState('')

  const update = useCallback(
    (key: string, value: string) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (value) next.set(key, value)
          else next.delete(key)
          return next
        },
        { replace: true },
      )
    },
    [setParams],
  )

  // Debounce typing into the search box.
  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.trim() !== search) update('q', query.trim())
    }, 250)
    return () => clearTimeout(timer)
  }, [query, search, update])

  useEffect(() => {
    let cancelled = false
    api
      .listRecipes({ search, tag, favorite: favorites, ordering: sort })
      .then((result) => {
        if (!cancelled) {
          setRecipes(result)
          setError('')
        }
      })
      .catch((err: Error) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [search, tag, favorites, sort])

  useEffect(() => {
    api.tags().then(setTags).catch(() => setTags([]))
  }, [])

  const filtering = Boolean(search || tag || favorites)

  return (
    <div className="library">
      <div className="library-toolbar">
        <input
          type="search"
          className="search"
          placeholder="Search recipes, ingredients, tags…"
          aria-label="Search recipes"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <select aria-label="Sort by" value={sort} onChange={(event) => update('sort', event.target.value === 'newest' ? '' : event.target.value)}>
          {SORTS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="chips-row" role="toolbar" aria-label="Filters">
        <button type="button" className={`filter-chip${favorites ? ' active' : ''}`} onClick={() => update('fav', favorites ? '' : '1')}>
          ♥ Favorites
        </button>
        {tags.map((t) => (
          <button
            key={t.name}
            type="button"
            className={`filter-chip${tag.toLowerCase() === t.name.toLowerCase() ? ' active' : ''}`}
            onClick={() => update('tag', tag.toLowerCase() === t.name.toLowerCase() ? '' : t.name)}
          >
            {t.name} <span className="count">{t.count}</span>
          </button>
        ))}
      </div>

      {error && <div className="alert error">{error}</div>}

      {recipes === null && !error && <p className="muted">Loading…</p>}

      {recipes && recipes.length === 0 && !filtering && (
        <div className="empty">
          <h2>Your recipe box is empty</h2>
          <p>Import a recipe from a link, a PDF, or a screenshot, or type one in.</p>
          <div className="empty-actions">
            <Link to="/import" className="button primary">
              Import a recipe
            </Link>
            <Link to="/recipes/new" className="button">
              Write one
            </Link>
          </div>
        </div>
      )}

      {recipes && recipes.length === 0 && filtering && <p className="muted">No recipes match.</p>}

      {recipes && recipes.length > 0 && (
        <>
          <p className="muted small">
            {recipes.length} recipe{recipes.length === 1 ? '' : 's'}
          </p>
          <div className="grid">
            {recipes.map((recipe) => (
              <RecipeCard key={recipe.id} recipe={recipe} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
