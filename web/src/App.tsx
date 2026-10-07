import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import Home from './pages/Home';
import Login from './pages/Login';
import Register from './pages/Register';
import DocumentAnalysis from './pages/DocumentAnalysis';
import Schemas from './pages/Schemas';
import SchemaDetail from './pages/SchemaDetail';
import ApiKeys from './pages/ApiKeys';
import ExportsUsage from './pages/ExportsUsage';
import { AuthProvider, useAuth } from './context/AuthContext';

const queryClient = new QueryClient();

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8">Loading...</div>;
  if (!user) return <Navigate to="/login" />;
  return <>{children}</>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/" element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
              <Route index element={<Home />} />
              <Route path="documents/:id/analysis" element={<DocumentAnalysis />} />
              <Route path="schemas" element={<Schemas />} />
              <Route path="schemas/:id" element={<SchemaDetail />} />
              <Route path="api-keys" element={<ApiKeys />} />
              <Route path="exports-usage" element={<ExportsUsage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
