import { createContext, useContext } from 'react'
import type { Me, Profile } from './types'

export interface AuthValue {
  user: Me | null
  /** True until the first "who am I?" call comes back. */
  loading: boolean
  signIn: (username: string, password: string) => Promise<void>
  signUp: (data: { username: string; password: string; email?: string; display_name?: string }) => Promise<void>
  signOut: () => Promise<void>
  /** Replaces the signed-in user after a profile change. */
  setUser: (user: Me) => void
}

export const AuthContext = createContext<AuthValue | null>(null)

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}

/** The signed-in user's own profile, or null when signed out. */
export function useMyProfile(): Profile | null {
  return useAuth().user?.profile ?? null
}
