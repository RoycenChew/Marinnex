// @ts-nocheck
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { Link } from 'react-router-dom';

export default function Schemas() {
  const { data: schemas, isLoading } = useQuery({
    queryKey: ['schemas'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/v1/schemas');
      if (error) throw error;
      return data;
    }
  });

  if (isLoading) return <div className="p-6">Loading schemas...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Schemas</h1>
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 divide-y">
        {schemas?.map((s: any) => (
          <div key={s.id || s.schema_id} className="p-4 flex justify-between items-center hover:bg-gray-50">
            <div>
              <Link to={`/schemas/${s.id || s.schema_id}`} className="font-medium text-primary-dark hover:underline">
                {s.name}
              </Link>
              <p className="text-sm text-gray-500">Version {s.version}</p>
            </div>
          </div>
        ))}
        {(!schemas || schemas.length === 0) && (
          <div className="p-4 text-gray-500 text-center">No schemas found.</div>
        )}
      </div>
    </div>
  );
}
