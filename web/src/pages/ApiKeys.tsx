// @ts-nocheck
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { Key } from 'lucide-react';

export default function ApiKeys() {
  const { data: keys, isLoading } = useQuery({
    queryKey: ['apiKeys'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/v1/api-keys');
      if (error) throw error;
      return data;
    }
  });

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">API Keys</h1>
        <button className="bg-primary-dark text-white px-4 py-2 rounded font-medium flex items-center gap-2 hover:bg-primary-light">
          <Key className="w-4 h-4" /> Generate Key
        </button>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Prefix</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mode</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created At</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Expires At</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Used</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Revoked At</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {isLoading ? (
              <tr><td colSpan={7} className="px-6 py-4 text-center">Loading...</td></tr>
            ) : keys?.map((k: any) => (
              <tr key={k.id}>
                <td className="px-6 py-4 text-sm font-medium">{k.name || '-'}</td>
                <td className="px-6 py-4 text-sm font-mono text-gray-600">{k.prefix}</td>
                <td className="px-6 py-4 text-sm">{k.mode}</td>
                <td className="px-6 py-4 text-sm text-gray-500">{k.created_at ? new Date(k.created_at).toLocaleDateString() : '-'}</td>
                <td className="px-6 py-4 text-sm text-gray-500">{k.expires_at ? new Date(k.expires_at).toLocaleDateString() : '-'}</td>
                <td className="px-6 py-4 text-sm text-gray-500">{k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : '-'}</td>
                <td className="px-6 py-4 text-sm text-gray-500">{k.revoked_at ? new Date(k.revoked_at).toLocaleDateString() : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
