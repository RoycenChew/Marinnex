// @ts-nocheck
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';

export default function SchemaDetail() {
  const { id } = useParams<{ id: string }>();

  const { data: schema, isLoading } = useQuery({
    queryKey: ['schema', id],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/v1/schemas/{schema_id}', {
        params: { path: { schema_id: id! } }
      });
      if (error) throw error;
      return data;
    }
  });

  if (isLoading) return <div className="p-6">Loading schema...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">{schema?.name || 'Schema Detail'}</h1>
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <h2 className="text-lg font-medium mb-4">Versions</h2>
        <ul className="space-y-2">
          {schema?.versions?.map((v: any) => (
            <li key={v.version} className="p-3 border rounded">
              <div className="font-medium">Version {v.version}</div>
              <div className="text-sm text-gray-500">Test Run Status: {v.test_run_status}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
