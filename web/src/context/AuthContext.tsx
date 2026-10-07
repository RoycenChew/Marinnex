import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { apiClient } from '../api/client'
import type { components } from '../api/v1'

/**
 * Session state.
 *
 * The session itself is an httpOnly cookie the browser holds; nothing here is
 * persisted. Rule 2.13 and the UI spec both say so: no extracted value and no
 * credential goes to localStorage, and the project id is re-derived from
 * `/auth/me` on every load rather than remembered.
 */

type MeResponse = components['schemas']['MeResponse']
export type User = MeResponse['user']
export type Project = MeResponse['projects'][number]

type AuthContextValue = {
  user: User | null
  projects: Project[]
  activeProjectId: string | null
  setActiveProjectId: (id: string) => void
  loading: boolean
  checkAuth: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const checkAuth = useCallback(async () => {
    try {
      const { data } = await apiClient.GET('/v1/auth/me')
      if (data) {
        setUser(data.user)
        setProjects(data.projects)
        // Default to the first project, which is what every UI route does when
        // no `?project_id=` is given.
        setActiveProjectId((current) => current ?? data.projects[0]?.id ?? null)
      } else {
        setUser(null)
        setProjects([])
      }
    } catch {
      // A failed /auth/me means "not signed in", which is a normal first load,
      // not an error worth surfacing.
      setUser(null)
      setProjects([])
    } finally {
      setLoading(false)
    }
  }, [])

  const logout = useCallback(async () => {
    await apiClient.POST('/v1/auth/logout')
    setUser(null)
    setProjects([])
    setActiveProjectId(null)
  }, [])

  useEffect(() => {
    void checkAuth()
  }, [checkAuth])

  const value = useMemo(
    () => ({
      user,
      projects,
      activeProjectId,
      setActiveProjectId,
      loading,
      checkAuth,
      logout,
    }),
    [user, projects, activeProjectId, loading, checkAuth, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
