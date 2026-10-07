// @ts-nocheck
import React, { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { apiClient } from '../api/client';
type User = {
  id: string;
  email: string;
};
type Project = {
  id: string;
  name: string;
};
type AuthContextType = {
  user: User | null;
  projects: Project[];
  activeProjectId: string | null;
  setActiveProjectId: (id: string) => void;
  loading: boolean;
  checkAuth: () => Promise<void>;
  logout: () => Promise<void>;
};
const AuthContext = createContext<AuthContextType | undefined>(undefined);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const checkAuth = async () => {
    try {
      const { data, error } = await apiClient.GET('/v1/auth/me');
      if (data) {
        setUser(data.user as User);
        setProjects(data.projects as Project[]);
        if (!activeProjectId && data.projects && data.projects.length > 0) {
          setActiveProjectId(data.projects[0].id);
        }
      } else {
        setUser(null);
        setProjects([]);
      }
    } catch (e) {
      setUser(null);
      setProjects([]);
    } finally {
      setLoading(false);
    }
  };
  const logout = async () => {
    await apiClient.POST('/v1/auth/logout');
    setUser(null);
    setProjects([]);
    setActiveProjectId(null);
  };
  useEffect(() => {
    checkAuth();
  }, []);
  return (
    <AuthContext.Provider value={{ user, projects, activeProjectId, setActiveProjectId, loading, checkAuth, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
