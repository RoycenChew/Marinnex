// @ts-nocheck
import { useAuth } from '../../context/AuthContext';
import { LogOut, User } from 'lucide-react';

export default function TopBar() {
  const { user, projects, activeProjectId, setActiveProjectId, logout } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0 z-10 shadow-sm">
      <div className="flex items-center gap-4">
        <span className="text-sm font-medium text-gray-500">Project:</span>
        <select
          value={activeProjectId || ''}
          onChange={(e) => setActiveProjectId(e.target.value)}
          className="bg-gray-50 border border-gray-200 text-gray-900 text-sm rounded-md focus:ring-primary-light focus:border-primary-light block w-full p-2 outline-none"
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 px-3 py-1.5 rounded-full border border-gray-200">
          <User className="w-4 h-4 text-gray-400" />
          {user?.email}
        </div>
        <button
          onClick={() => logout()}
          className="text-gray-400 hover:text-red-500 transition-colors p-1.5 hover:bg-red-50 rounded-full"
          title="Logout"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
