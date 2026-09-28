import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api'
import { AuthContext } from '../auth'
import type { Me } from '../types'

/** Holds who's signed in. One "who am I?" call on load; the rest is sign in/out. */
export default function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    api
      .me()
      .then((me) => !cancelled && setUser(me))
      .catch(() => {})
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  const signIn = useCallback(async (username: string, password: string) => {
    setUser(await api.login(username, password))
  }, [])

  const signUp = useCallback(async (data: Parameters<typeof api.register>[0]) => {
    setUser(await api.register(data))
  }, [])

  const signOut = useCallback(async () => {
    await api.logout()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, loading, signIn, signUp, signOut, setUser }),
    [user, loading, signIn, signUp, signOut],
  )
  return <AuthContext value={value}>{children}</AuthContext>
}
