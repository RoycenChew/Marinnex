import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'
import AppLayout from './components/layout/AppLayout'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ThemeProvider, useTheme } from './lib/theme'
import ApiKeys from './pages/ApiKeys'
import DocumentAnalysis from './pages/DocumentAnalysis'
import ExportsUsage from './pages/ExportsUsage'
import Home from './pages/Home'
import Login from './pages/Login'
import Register from './pages/Register'
import SchemaDetail from './pages/SchemaDetail'
import Schemas from './pages/Schemas'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // The data here is a person's own documents; refetching on every window
      // focus makes a review screen flicker while they are reading it.
      refetchOnWindowFocus: false,
      staleTime: 10_000,
      retry: 1,
    },
  },
})

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--surface-page)]">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--border-subtle)] border-t-[var(--accent-solid)]" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

/** Sonner has to know the theme, or toasts arrive white on a dark page. */
function ThemedToaster() {
  const { resolved } = useTheme()
  return (
    <Toaster
      theme={resolved}
      position="bottom-right"
      closeButton
      toastOptions={{
        style: {
          background: 'var(--surface-overlay)',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
        },
      }}
    />
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Home />} />
                <Route path="documents/:id/analysis" element={<DocumentAnalysis />} />
                <Route path="schemas" element={<Schemas />} />
                <Route path="schemas/:id" element={<SchemaDetail />} />
                <Route path="api-keys" element={<ApiKeys />} />
                <Route path="exports-usage" element={<ExportsUsage />} />
              </Route>
            </Routes>
          </BrowserRouter>
          <ThemedToaster />
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
