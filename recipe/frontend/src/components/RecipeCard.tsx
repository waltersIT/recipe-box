import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { formatMinutes } from '../lib/format'
import type { RecipeSummary } from '../types'
import Avatar from './Avatar'
import LikeButton from './LikeButton'
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

interface Props {
  recipe: RecipeSummary
  /** On a profile, every card is by the same person, so their name is left off. */
  hideOwner?: boolean
  onLike?: (liked: boolean, count: number) => void
}

export default function RecipeCard({ recipe, hideOwner, onLike }: Props) {
  const time = formatMinutes(recipe.total_time || (recipe.prep_time ?? 0) + (recipe.cook_time ?? 0))
  return (
    <div className="card">
      <Link to={`/recipes/${recipe.id}`} className="card-link">
        <div className="card-image">
          {recipe.image ? <img src={recipe.image} alt="" loading="lazy" /> : <RecipePlaceholder title={recipe.title} />}
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
      <div className="card-foot">
        {!hideOwner && recipe.owner && (
          <Link to={`/u/${recipe.owner.username}`} className="byline">
            <Avatar user={recipe.owner} size={22} />
            <span className="truncate">{recipe.owner.name}</span>
          </Link>
        )}
        {!hideOwner && !recipe.owner && <span className="byline muted small">No account</span>}
        <LikeButton
          recipeId={recipe.id}
          liked={recipe.liked}
          count={recipe.like_count}
          size="sm"
          onChange={(liked, count) => onLike?.(liked, count)}
        />
      </div>
    </div>
  )
}
