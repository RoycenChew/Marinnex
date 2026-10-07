// @ts-nocheck
import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiClient } from '../api/client';
import { Link, useNavigate } from 'react-router-dom';

export default function Login() {
  const [email, setEmail] = useState('dev@fdip.local');
  const [password, setPassword] = useState('devpass');
  const [error, setError] = useState('');
  const { checkAuth } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      const { error: apiError } = await apiClient.POST('/v1/auth/login', {
        body: { email, password }
      });
      if (apiError) {
        setError(apiError.detail || 'Login failed');
      } else {
        await checkAuth();
        navigate('/');
      }
    } catch (err: any) {
      setError(err.message || 'Login failed');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="bg-white p-8 rounded-lg shadow-sm border border-gray-200 w-full max-w-md">
        <h1 className="text-2xl font-bold text-center text-primary-dark tracking-tight mb-6">Marinnex</h1>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {error && <div className="text-red-600 bg-red-50 p-3 rounded text-sm border border-red-100">{error}</div>}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              className="w-full border border-gray-300 rounded p-2 focus:ring-primary-light focus:border-primary-light outline-none"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              className="w-full border border-gray-300 rounded p-2 focus:ring-primary-light focus:border-primary-light outline-none"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button
            type="submit"
            className="w-full bg-primary-dark text-white p-2.5 rounded font-medium hover:bg-primary-light transition-colors mt-2"
          >
            Sign In
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-gray-600">
          Don't have an account? <Link to="/register" className="text-primary-dark font-medium hover:underline">Register</Link>
        </p>
      </div>
    </div>
  );
}
