import type { CSSProperties } from 'react'
import type { UserBrief } from '../types'

/** A user's photo, or their initial on a colour picked from their name. */
export default function Avatar({ user, size = 32 }: { user: Pick<UserBrief, 'name' | 'avatar'>; size?: number }) {
  if (user.avatar) {
    return <img className="avatar" src={user.avatar} alt="" width={size} height={size} style={{ width: size, height: size }} />
  }
  let hash = 0
  for (const char of user.name) hash = (hash * 31 + char.charCodeAt(0)) | 0
  const style = { width: size, height: size, fontSize: size * 0.45, '--hue': Math.abs(hash) % 360 } as CSSProperties
  return (
    <span className="avatar initials" style={style} aria-hidden="true">
      {user.name.trim().charAt(0).toUpperCase() || '?'}
    </span>
  )
}
