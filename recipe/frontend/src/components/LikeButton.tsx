import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

interface Props {
  recipeId: number
  liked: boolean
  count: number
  onChange: (liked: boolean, count: number) => void
  size?: 'sm' | 'md'
}

/** The heart on a recipe. Liking needs an account, so it sends you to sign in. */
export default function LikeButton({ recipeId, liked, count, onChange, size = 'md' }: Props) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)

  async function toggle() {
    if (!user) {
      navigate(`/login?next=${encodeURIComponent(`/recipes/${recipeId}`)}`)
      return
    }
    setBusy(true)
    const next = !liked
    onChange(next, count + (next ? 1 : -1)) // optimistic
    try {
      const result = await api.like(recipeId, next)
      onChange(result.liked, result.like_count)
    } catch {
      onChange(liked, count)
    } finally {
      setBusy(false)
    }
  }

  return (
    <button
      type="button"
      className={`like-button ${size}${liked ? ' on' : ''}`}
      aria-pressed={liked}
      aria-label={liked ? 'Unlike this recipe' : 'Like this recipe'}
      disabled={busy}
      onClick={toggle}
    >
      <span aria-hidden="true">{liked ? '♥' : '♡'}</span>
      {count > 0 && <span className="like-count">{count}</span>}
    </button>
  )
}
