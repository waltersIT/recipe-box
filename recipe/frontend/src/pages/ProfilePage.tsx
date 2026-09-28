import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import Avatar from '../components/Avatar'
import RecipeCard from '../components/RecipeCard'
import type { Profile, RecipeSummary } from '../types'

const SORTS = [
  { value: 'newest', label: 'Newest' },
  { value: 'liked', label: 'Most liked' },
  { value: 'viewed', label: 'Most viewed' },
  { value: 'title', label: 'A–Z' },
]

function EditProfile({ profile, onDone }: { profile: Profile; onDone: (updated: Profile) => void }) {
  const { setUser } = useAuth()
  const [displayName, setDisplayName] = useState(profile.display_name)
  const [bio, setBio] = useState(profile.bio)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const photoInput = useRef<HTMLInputElement>(null)

  async function run(work: () => Promise<{ profile: Profile }>) {
    setBusy(true)
    setError('')
    try {
      const me = await work()
      setUser(me as Parameters<typeof setUser>[0])
      onDone(me.profile)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function save(event: FormEvent) {
    event.preventDefault()
    void run(() => api.updateProfile({ display_name: displayName, bio }))
  }

  return (
    <form className="panel profile-edit" onSubmit={save}>
      <h2>Edit your profile</h2>
      <div className="field">
        <label htmlFor="display_name">Display name</label>
        <input id="display_name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        <span className="hint">Shown on your recipes. Your username stays @{profile.username}.</span>
      </div>
      <div className="field">
        <label htmlFor="bio">About</label>
        <textarea id="bio" rows={3} maxLength={600} value={bio} onChange={(e) => setBio(e.target.value)} />
      </div>
      <div className="field">
        <span className="label">Photo</span>
        <div className="button-row">
          <input
            ref={photoInput}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void run(() => api.uploadAvatar(file))
              e.target.value = ''
            }}
          />
          <button type="button" className="button small" disabled={busy} onClick={() => photoInput.current?.click()}>
            {profile.avatar ? 'Replace photo' : 'Add photo'}
          </button>
          {profile.avatar && (
            <button type="button" className="button small danger-text" disabled={busy} onClick={() => void run(api.deleteAvatar)}>
              Remove
            </button>
          )}
        </div>
      </div>
      {error && <div className="alert error">{error}</div>}
      <div className="button-row">
        <button type="submit" className="button primary" disabled={busy}>
          {busy ? 'Saving…' : 'Save profile'}
        </button>
        <button type="button" className="button" disabled={busy} onClick={() => onDone(profile)}>
          Done
        </button>
      </div>
    </form>
  )
}

export default function ProfilePage() {
  const { username } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  // Both are stored with the profile they belong to, so moving between
  // profiles never shows the previous one's name or recipes.
  const [loaded, setLoaded] = useState<{ username: string; profile: Profile } | null>(null)
  const [loadedRecipes, setLoadedRecipes] = useState<{ key: string; data: RecipeSummary[] } | null>(null)
  const [sort, setSort] = useState('newest')
  const [editingUser, setEditingUser] = useState('')
  const [error, setError] = useState('')

  const profile = loaded && loaded.username === username ? loaded.profile : null
  const recipeKey = `${username}:${sort}`
  const recipes = loadedRecipes?.key === recipeKey ? loadedRecipes.data : null
  const editing = editingUser === username

  useEffect(() => {
    let cancelled = false
    api
      .profile(username!)
      .then((data) => !cancelled && (setLoaded({ username: username!, profile: data }), setError('')))
      .catch((err: Error) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [username])

  useEffect(() => {
    let cancelled = false
    api
      .profileRecipes(username!, sort)
      .then((data) => !cancelled && setLoadedRecipes({ key: recipeKey, data }))
      .catch(() => !cancelled && setLoadedRecipes({ key: recipeKey, data: [] }))
    return () => {
      cancelled = true
    }
  }, [username, sort, recipeKey])

  async function toggleFollow() {
    if (!user) {
      navigate(`/login?next=${encodeURIComponent(`/u/${username}`)}`)
      return
    }
    try {
      setLoaded({ username: username!, profile: await api.follow(profile!.username, !profile!.is_following) })
    } catch (err) {
      setError((err as Error).message)
    }
  }

  function updateCard(id: number, liked: boolean, count: number) {
    setLoadedRecipes((prev) =>
      prev ? { ...prev, data: prev.data.map((r) => (r.id === id ? { ...r, liked, like_count: count } : r)) } : prev,
    )
  }

  if (error) return <div className="alert error">{error}</div>
  if (!profile) return <p className="muted">Loading…</p>

  return (
    <div className="profile-page">
      <header className="profile-header">
        <Avatar user={profile} size={88} />
        <div className="profile-text">
          <h1>{profile.name}</h1>
          <p className="muted">@{profile.username}</p>
          {profile.bio && <p className="profile-bio">{profile.bio}</p>}
          <ul className="profile-stats">
            <li>
              <strong>{profile.recipe_count}</strong> recipe{profile.recipe_count === 1 ? '' : 's'}
            </li>
            <li>
              <strong>{profile.follower_count}</strong> follower{profile.follower_count === 1 ? '' : 's'}
            </li>
            <li>
              <strong>{profile.following_count}</strong> following
            </li>
          </ul>
        </div>
        <div className="button-row">
          {profile.is_me ? (
            <button type="button" className="button" onClick={() => setEditingUser(editing ? '' : username!)}>
              {editing ? 'Close' : 'Edit profile'}
            </button>
          ) : (
            <button type="button" className={`button${profile.is_following ? '' : ' primary'}`} onClick={toggleFollow}>
              {profile.is_following ? 'Following' : 'Follow'}
            </button>
          )}
        </div>
      </header>

      {editing && profile.is_me && (
        <EditProfile
          profile={profile}
          onDone={(updated) => {
            setLoaded({ username: username!, profile: updated })
            setEditingUser('')
          }}
        />
      )}

      <div className="section-head">
        <h2>{profile.is_me ? 'Your recipes' : 'Recipes'}</h2>
        {recipes && recipes.length > 1 && (
          <select aria-label="Sort recipes" value={sort} onChange={(e) => setSort(e.target.value)}>
            {SORTS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
      </div>

      {recipes === null && <p className="muted">Loading…</p>}
      {recipes?.length === 0 && (
        <div className="empty">
          <p className="muted">
            {profile.is_me ? "You haven't uploaded a recipe yet." : `${profile.name} hasn't uploaded a recipe yet.`}
          </p>
          {profile.is_me && (
            <div className="empty-actions">
              <Link to="/import" className="button primary">
                Import a recipe
              </Link>
              <Link to="/recipes/new" className="button">
                Write one
              </Link>
            </div>
          )}
        </div>
      )}
      {recipes && recipes.length > 0 && (
        <div className="grid">
          {recipes.map((recipe) => (
            <RecipeCard
              key={recipe.id}
              recipe={recipe}
              hideOwner
              onLike={(liked, count) => updateCard(recipe.id, liked, count)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
