import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import RecipeCard from '../components/RecipeCard'
import type { HomeFeed, RecipeSummary, TagCount } from '../types'

const SORTS = [
  { value: 'newest', label: 'Newest' },
  { value: 'popular', label: 'Most popular' },
  { value: 'liked', label: 'Most liked' },
  { value: 'viewed', label: 'Most viewed' },
  { value: 'title', label: 'A–Z' },
  { value: 'rating', label: 'Top rated' },
]

function Grid({ recipes, onLike }: { recipes: RecipeSummary[]; onLike: (id: number, liked: boolean, count: number) => void }) {
  return (
    <div className="grid">
      {recipes.map((recipe) => (
        <RecipeCard key={recipe.id} recipe={recipe} onLike={(liked, count) => onLike(recipe.id, liked, count)} />
      ))}
    </div>
  )
}

export default function HomePage() {
  const { user } = useAuth()
  const accountDeleted = (useLocation().state as { accountDeleted?: boolean } | null)?.accountDeleted
  const [params, setParams] = useSearchParams()
  const search = params.get('q') ?? ''
  const tag = params.get('tag') ?? ''
  const liked = params.get('liked') === '1'
  const mine = params.get('mine') === '1'
  const sort = params.get('sort') ?? ''

  const [query, setQuery] = useState(search)
  // Results are stored with the request that produced them, so a stale list
  // isn't shown while the next one is on its way.
  const [feed, setFeed] = useState<{ key: string; data: HomeFeed } | null>(null)
  const [results, setResults] = useState<{ key: string; data: RecipeSummary[] } | null>(null)
  const [tags, setTags] = useState<TagCount[]>([])
  const [error, setError] = useState('')

  // With no search or filter, the landing page shows its own sections instead
  // of one long list.
  const browsing = Boolean(search || tag || liked || mine || sort)

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

  const requestKey = JSON.stringify([search, tag, liked, mine, sort, user?.username ?? ''])
  const shownFeed = !browsing && feed?.key === requestKey ? feed.data : null
  const shownResults = browsing && results?.key === requestKey ? results.data : null

  useEffect(() => {
    let cancelled = false
    const fail = (err: Error) => !cancelled && setError(err.message)
    if (!browsing) {
      api
        .home()
        .then((data) => !cancelled && (setFeed({ key: requestKey, data }), setError('')))
        .catch(fail)
    } else {
      api
        .listRecipes({ search, tag, liked, mine, ordering: sort })
        .then((data) => !cancelled && (setResults({ key: requestKey, data }), setError('')))
        .catch(fail)
    }
    return () => {
      cancelled = true
    }
    // The user is part of the key, so the feed and hearts refresh on sign in or out.
  }, [browsing, search, tag, liked, mine, sort, requestKey])

  useEffect(() => {
    api.tags().then(setTags).catch(() => setTags([]))
  }, [])

  function onLike(id: number, isLiked: boolean, count: number) {
    const apply = (list: RecipeSummary[]) =>
      list.map((r) => (r.id === id ? { ...r, liked: isLiked, like_count: count } : r))
    setResults((prev) => (prev ? { ...prev, data: apply(prev.data) } : prev))
    setFeed((prev) =>
      prev
        ? { ...prev, data: { ...prev.data, following: apply(prev.data.following), recommended: apply(prev.data.recommended) } }
        : prev,
    )
  }

  const chip = (key: string, on: boolean, label: string) => (
    <button type="button" className={`filter-chip${on ? ' active' : ''}`} onClick={() => update(key, on ? '' : '1')}>
      {label}
    </button>
  )

  return (
    <div className="library">
      {accountDeleted && <div className="alert info">Your account and everything in it have been deleted.</div>}
      <div className="library-toolbar">
        <input
          type="search"
          className="search"
          placeholder="Search recipes, ingredients, tags…"
          aria-label="Search recipes"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <select aria-label="Sort by" value={sort} onChange={(event) => update('sort', event.target.value)}>
          <option value="">Sort</option>
          {SORTS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="chips-row" role="toolbar" aria-label="Filters">
        {user && chip('liked', liked, '♥ Liked')}
        {user && chip('mine', mine, 'My recipes')}
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

      {browsing ? (
        <>
          {shownResults === null && !error && <p className="muted">Loading…</p>}
          {shownResults?.length === 0 && <p className="muted">No recipes match.</p>}
          {shownResults && shownResults.length > 0 && (
            <>
              <p className="muted small">
                {shownResults.length} recipe{shownResults.length === 1 ? '' : 's'}
              </p>
              <Grid recipes={shownResults} onLike={onLike} />
            </>
          )}
        </>
      ) : (
        <>
          {shownFeed === null && !error && <p className="muted">Loading…</p>}

          {shownFeed?.recipe_count === 0 && (
            <div className="empty">
              <h2>No recipes yet</h2>
              <p>
                {user
                  ? 'Import one from a link, a PDF, or a screenshot, or type one in.'
                  : 'Create an account to add the first one.'}
              </p>
              <div className="empty-actions">
                {user ? (
                  <>
                    <Link to="/import" className="button primary">
                      Import a recipe
                    </Link>
                    <Link to="/recipes/new" className="button">
                      Write one
                    </Link>
                  </>
                ) : (
                  <Link to="/signup" className="button primary">
                    Create an account
                  </Link>
                )}
              </div>
            </div>
          )}

          {shownFeed && shownFeed.following.length > 0 && (
            <section className="feed-section">
              <div className="section-head">
                <h2>From people you follow</h2>
                <Link className="small" to="/?sort=newest">
                  Browse everything
                </Link>
              </div>
              <Grid recipes={shownFeed.following} onLike={onLike} />
            </section>
          )}

          {shownFeed && shownFeed.recommended.length > 0 && (
            <section className="feed-section">
              <div className="section-head">
                <h2>{shownFeed.following.length > 0 ? 'Popular in Recipe Box' : 'Recommended'}</h2>
                <span className="muted small">Most viewed and liked</span>
              </div>
              <Grid recipes={shownFeed.recommended} onLike={onLike} />
            </section>
          )}

          {shownFeed && user && shownFeed.following_count === 0 && shownFeed.recipe_count > 0 && (
            <p className="muted small">
              Follow someone from a recipe or their profile and their newest recipes show up here.
            </p>
          )}
          {shownFeed && !user && shownFeed.recipe_count > 0 && (
            <p className="muted small">
              <Link to="/signup">Create an account</Link> to like recipes, follow cooks, and add your own.
            </p>
          )}
        </>
      )}
    </div>
  )
}
