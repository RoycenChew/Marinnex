import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useParams,
} from 'react-router-dom'
import { Toaster } from 'sonner'
import AppLayout from './components/layout/AppLayout'
import PublicLayout from './components/layout/PublicLayout'
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
import Landing from './pages/public/Landing'
import Guide from './pages/public/Guide'
import Trust from './pages/public/Trust'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
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

/** Old links kept working: `/documents/:id/analysis` → `/app/documents/:id`. */
function LegacyDocumentRedirect() {
  const { id } = useParams()
  return <Navigate to={`/app/documents/${id}`} replace />
}

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
              {/*
                C8 — the public site needs no login, and must never call an
                authenticated endpoint. It sits at the root; the product moved
                under /app.
              */}
              <Route element={<PublicLayout />}>
                <Route index element={<Landing />} />
                <Route path="guide" element={<Guide />} />
                <Route path="trust" element={<Trust />} />
              </Route>

              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />

              <Route
                path="/app"
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Home />} />
                <Route path="documents/:id" element={<DocumentAnalysis />} />
                <Route path="schemas" element={<Schemas />} />
                <Route path="schemas/:id" element={<SchemaDetail />} />
                <Route path="api-keys" element={<ApiKeys />} />
                <Route path="usage" element={<ExportsUsage />} />
              </Route>

              {/* Links from before the split. */}
              <Route
                path="/documents/:id/analysis"
                element={<LegacyDocumentRedirect />}
              />
              <Route path="/schemas" element={<Navigate to="/app/schemas" replace />} />
              <Route
                path="/schemas/:id"
                element={<Navigate to="/app/schemas" replace />}
              />
              <Route
                path="/api-keys"
                element={<Navigate to="/app/api-keys" replace />}
              />
              <Route
                path="/exports-usage"
                element={<Navigate to="/app/usage" replace />}
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
          <ThemedToaster />
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
