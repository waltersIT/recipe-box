import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { RecipePlaceholder } from '../components/RecipeCard'
import StarRating from '../components/StarRating'
import { IMPORT_METHOD_LABELS, formatMinutes, headingText, hostname, isHeading } from '../lib/format'
import { scaleIngredient } from '../lib/scale'
import type { Recipe } from '../types'

const SCALES = [0.5, 1, 2, 3]

export default function RecipePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [recipe, setRecipe] = useState<Recipe | null>(null)
  const [error, setError] = useState('')
  const [scale, setScale] = useState(1)
  const [checked, setChecked] = useState<Set<number>>(new Set())
  const [currentStep, setCurrentStep] = useState<number | null>(null)
  const [awake, setAwake] = useState(false)
  const wakeLock = useRef<WakeLockSentinel | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .getRecipe(id!)
      .then((data) => !cancelled && setRecipe(data))
      .catch((err: Error) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [id])

  useEffect(() => () => void wakeLock.current?.release(), [])

  if (error) return <div className="alert error">{error}</div>
  if (!recipe || String(recipe.id) !== id) return <p className="muted">Loading…</p>

  async function patch(changes: Partial<Pick<Recipe, 'rating' | 'is_favorite'>>) {
    setRecipe((prev) => (prev ? { ...prev, ...changes } : prev))
    try {
      setRecipe(await api.updateRecipe(recipe!.id, changes))
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function remove() {
    if (!confirm(`Delete “${recipe!.title}”? This can't be undone.`)) return
    try {
      await api.deleteRecipe(recipe!.id)
      navigate('/')
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function toggleAwake() {
    if (awake) {
      await wakeLock.current?.release()
      wakeLock.current = null
      setAwake(false)
      return
    }
    try {
      wakeLock.current = await navigator.wakeLock.request('screen')
      wakeLock.current.addEventListener('release', () => setAwake(false))
      setAwake(true)
    } catch {
      alert("This browser can't keep the screen on.")
    }
  }

  const times = [
    ['Prep', recipe.prep_time],
    ['Cook', recipe.cook_time],
    ['Total', recipe.total_time],
  ].filter(([, minutes]) => minutes) as [string, number][]

  // Step numbers skip section headings.
  const stepNumber = (index: number) => recipe.instructions.slice(0, index + 1).filter((line) => !isHeading(line)).length

  return (
    <article className="recipe">
      <header className="recipe-hero">
        <div className="recipe-hero-image">
          {recipe.image ? <img src={recipe.image} alt="" /> : <RecipePlaceholder title={recipe.title} />}
        </div>
        <div className="recipe-hero-text">
          <h1>{recipe.title}</h1>
          <div className="recipe-actions-row">
            <StarRating value={recipe.rating} onChange={(rating) => patch({ rating })} />
            <button
              type="button"
              className={`icon-button fav${recipe.is_favorite ? ' on' : ''}`}
              aria-pressed={recipe.is_favorite}
              onClick={() => patch({ is_favorite: !recipe.is_favorite })}
            >
              {recipe.is_favorite ? '♥ Favorite' : '♡ Favorite'}
            </button>
          </div>
          {recipe.description && <p className="description">{recipe.description}</p>}
          <dl className="facts">
            {recipe.servings && (
              <div>
                <dt>Serves</dt>
                <dd>{recipe.servings}</dd>
              </div>
            )}
            {times.map(([label, minutes]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{formatMinutes(minutes)}</dd>
              </div>
            ))}
          </dl>
          {recipe.tags.length > 0 && (
            <div className="tags">
              {recipe.tags.map((tag) => (
                <Link key={tag} to={`/?tag=${encodeURIComponent(tag)}`} className="chip">
                  {tag}
                </Link>
              ))}
            </div>
          )}
          <p className="source muted small">
            {recipe.source_url ? (
              <>
                From{' '}
                <a href={recipe.source_url} target="_blank" rel="noreferrer">
                  {recipe.source_name || hostname(recipe.source_url)}
                </a>
              </>
            ) : recipe.source_name ? (
              <>From {recipe.source_name}</>
            ) : (
              IMPORT_METHOD_LABELS[recipe.import_method]
            )}
            {recipe.author && <> · by {recipe.author}</>}
          </p>
          <div className="button-row">
            <Link to={`/recipes/${recipe.id}/edit`} className="button">
              Edit
            </Link>
            {'wakeLock' in navigator && (
              <button type="button" className={`button${awake ? ' primary' : ''}`} onClick={toggleAwake}>
                {awake ? 'Screen stays on' : 'Keep screen on'}
              </button>
            )}
            <button type="button" className="button danger-text" onClick={remove}>
              Delete
            </button>
          </div>
        </div>
      </header>

      <div className="recipe-body">
        <section className="ingredients">
          <div className="section-head">
            <h2>Ingredients</h2>
            <div className="segmented" role="group" aria-label="Scale recipe">
              {SCALES.map((value) => (
                <button key={value} type="button" className={scale === value ? 'active' : ''} onClick={() => setScale(value)}>
                  {value === 0.5 ? '½' : value}×
                </button>
              ))}
            </div>
          </div>
          {recipe.ingredients.length === 0 && <p className="muted">No ingredients yet.</p>}
          <ul className="ingredient-list">
            {recipe.ingredients.map((line, index) =>
              isHeading(line) ? (
                <li key={index} className="list-heading">
                  {headingText(line)}
                </li>
              ) : (
                <li key={index} className={checked.has(index) ? 'done' : ''}>
                  <label>
                    <input
                      type="checkbox"
                      checked={checked.has(index)}
                      onChange={() =>
                        setChecked((prev) => {
                          const next = new Set(prev)
                          if (next.has(index)) next.delete(index)
                          else next.add(index)
                          return next
                        })
                      }
                    />
                    <span>{scaleIngredient(line, scale)}</span>
                  </label>
                </li>
              ),
            )}
          </ul>
        </section>

        <section className="instructions">
          <h2>Instructions</h2>
          {recipe.instructions.length === 0 && <p className="muted">No instructions yet.</p>}
          <ol className="step-list">
            {recipe.instructions.map((line, index) => {
              if (isHeading(line)) {
                return (
                  <li key={index} className="list-heading">
                    {headingText(line)}
                  </li>
                )
              }
              return (
                <li
                  key={index}
                  className={currentStep === index ? 'current' : ''}
                  onClick={() => setCurrentStep(currentStep === index ? null : index)}
                >
                  <span className="step-number" aria-hidden="true">
                    {stepNumber(index)}
                  </span>
                  <p>{line}</p>
                </li>
              )
            })}
          </ol>

          {recipe.notes && (
            <>
              <h2>Notes</h2>
              <div className="notes">{recipe.notes}</div>
            </>
          )}

          {Object.keys(recipe.nutrition).length > 0 && (
            <>
              <h2>Nutrition</h2>
              <dl className="nutrition">
                {Object.entries(recipe.nutrition).map(([name, value]) => (
                  <div key={name}>
                    <dt>{name}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            </>
          )}

          {recipe.attachments.length > 0 && (
            <>
              <h2>Original files</h2>
              <ul className="attachments">
                {recipe.attachments.map((file) => (
                  <li key={file.id}>
                    <a href={file.url} target="_blank" rel="noreferrer">
                      {file.content_type.startsWith('image/') ? (
                        <img src={file.url} alt="" />
                      ) : (
                        <span className="file-icon">PDF</span>
                      )}
                      <span className="truncate">{file.original_name || 'File'}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>
    </article>
  )
}
