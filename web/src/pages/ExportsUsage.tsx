// @ts-nocheck
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';

export default function ExportsUsage() {
  const { data: usage, isLoading } = useQuery({
    queryKey: ['usage'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/v1/usage', {
         params: { query: { month: new Date().toISOString().slice(0, 7) } }
      });
      if (error) throw error;
      return data;
    }
  });

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Usage & Exports</h1>
      
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="text-sm text-gray-500 font-medium uppercase">Pages</div>
          <div className="text-2xl font-bold mt-2">{usage?.pages || 0}</div>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="text-sm text-gray-500 font-medium uppercase">Documents</div>
          <div className="text-2xl font-bold mt-2">{usage?.documents || 0}</div>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="text-sm text-gray-500 font-medium uppercase">AI Cost</div>
          <div className="text-2xl font-bold mt-2">USD {usage?.ai_cost_usd?.toFixed(2) || '0.00'}</div>
        </div>
      </div>
    </div>
  );
}
