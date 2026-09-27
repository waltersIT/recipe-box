import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { formatMinutes } from '../lib/format'
import type { RecipeSummary } from '../types'
import StarRating from './StarRating'

export function RecipePlaceholder({ title }: { title: string }) {
  // A stable hue per title so placeholders don't all look the same.
  let hash = 0
  for (const char of title) hash = (hash * 31 + char.charCodeAt(0)) | 0
  const hue = Math.abs(hash) % 360
  return (
    <div className="placeholder" style={{ '--hue': hue } as CSSProperties} aria-hidden="true">
      {title.trim().charAt(0).toUpperCase() || '?'}
    </div>
  )
}

export default function RecipeCard({ recipe }: { recipe: RecipeSummary }) {
  const time = formatMinutes(recipe.total_time || (recipe.prep_time ?? 0) + (recipe.cook_time ?? 0))
  return (
    <Link to={`/recipes/${recipe.id}`} className="card">
      <div className="card-image">
        {recipe.image ? <img src={recipe.image} alt="" loading="lazy" /> : <RecipePlaceholder title={recipe.title} />}
        {recipe.is_favorite && (
          <span className="card-fav" aria-label="Favorite">
            ♥
          </span>
        )}
      </div>
      <div className="card-body">
        <h3>{recipe.title}</h3>
        <div className="card-meta">
          {time && <span>{time}</span>}
          {recipe.source_name && <span className="muted truncate">{recipe.source_name}</span>}
        </div>
        {recipe.rating > 0 && <StarRating value={recipe.rating} size="sm" />}
      </div>
    </Link>
  )
}
