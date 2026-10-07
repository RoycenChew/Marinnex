// @ts-nocheck
import { NavLink } from 'react-router-dom';
import { Files, Key, Activity, Database } from 'lucide-react';
import clsx from 'clsx';

export default function Sidebar() {
  const navItems = [
    { to: '/', icon: Files, label: 'Documents' },
    { to: '/schemas', icon: Database, label: 'Schemas' },
    { to: '/api-keys', icon: Key, label: 'API Keys' },
    { to: '/exports-usage', icon: Activity, label: 'Usage & Exports' },
  ];

  return (
    <aside className="w-64 bg-white border-r border-gray-200 flex flex-col shadow-sm z-20">
      <div className="h-16 flex items-center px-6 border-b border-gray-200">
        <span className="text-xl font-bold text-primary-dark tracking-tight">Marinnex</span>
      </div>
      <nav className="flex-1 py-4 flex flex-col gap-1 px-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary-light/10 text-primary-dark'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              )
            }
          >
            <item.icon className="w-5 h-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
