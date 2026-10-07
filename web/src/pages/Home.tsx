// @ts-nocheck
import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiClient, API_ORIGIN } from '../api/client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { UploadCloud, File, AlertCircle, CheckCircle2, Loader2, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import clsx from 'clsx';

export default function Home() {
  const { activeProjectId } = useAuth();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');

  const { data: documentsData, refetch } = useQuery({
    queryKey: ['documents', activeProjectId],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/v1/documents', {
        params: { query: { project_id: activeProjectId || undefined } }
      });
      if (error) throw error;
      return data;
    },
    enabled: !!activeProjectId,
  });

  const documents = documentsData?.items || [];
  const hasProcessing = documents.some(d => d.status === 'processing');

  // Polling logic
  useEffect(() => {
    let interval: number | undefined;
    if (hasProcessing) {
      interval = window.setInterval(() => {
        refetch();
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [hasProcessing, refetch]);

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await apiClient.DELETE('/v1/documents/{document_id}', {
        params: { path: { document_id: id }, query: { project_id: activeProjectId || undefined } }
      });
      if (error) throw error;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    }
  });

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadError('');

    try {
      const formData = new FormData();
      formData.append('file', file);
      // Generate idempotency key
      const idempotencyKey = crypto.randomUUID();

      const response = await fetch(`${API_ORIGIN}/v1/documents${activeProjectId ? `?project_id=${activeProjectId}` : ''}`, {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey },
        body: formData,
        credentials: 'include'
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Upload failed');
      }
      
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    } catch (err: any) {
      setUploadError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const getStatusBadge = (status: string, code?: string) => {
    switch (status) {
      case 'completed': return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"><CheckCircle2 className="w-3 h-3 mr-1" /> Completed</span>;
      case 'needs_review': return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">Needs Review</span>;
      case 'processing': return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Processing</span>;
      case 'document_type_mismatch': 
      case 'unsupported':
      case 'failed':
        return <span title={code} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 cursor-help"><AlertCircle className="w-3 h-3 mr-1" /> {status}</span>;
      case 'rejected': return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">Rejected</span>;
      default: return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">{status}</span>;
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Documents</h1>
      </div>

      <div className="bg-white p-8 rounded-lg shadow-sm border border-gray-200 text-center">
        <div className="flex flex-col items-center justify-center">
          <UploadCloud className="w-12 h-12 text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Upload Document</h3>
          <p className="text-sm text-gray-500 mb-6">PDF, PNG, JPG up to 20MB</p>
          
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileChange}
            accept=".pdf,.png,.jpg,.jpeg"
            className="hidden"
          />
          <button 
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className={clsx(
              "px-4 py-2 rounded font-medium text-white transition-colors",
              uploading ? "bg-primary-light cursor-not-allowed" : "bg-primary-dark hover:bg-primary-light"
            )}
          >
            {uploading ? 'Uploading...' : 'Select File'}
          </button>
          {uploadError && <p className="mt-4 text-sm text-red-600 bg-red-50 p-2 rounded">{uploadError}</p>}
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Filename</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {documents.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-sm text-gray-500">
                  No documents found.
                </td>
              </tr>
            ) : documents.map((doc) => (
              <tr key={doc.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <File className="flex-shrink-0 h-5 w-5 text-gray-400 mr-3" />
                    <Link to={`/documents/${doc.id}/analysis`} className="text-sm font-medium text-primary-dark hover:underline">
                      {doc.filename}
                    </Link>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {doc.document_type || '-'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {getStatusBadge(doc.status)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {new Date(doc.created_at || '').toLocaleDateString()}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button 
                    onClick={() => deleteMutation.mutate(doc.id!)}
                    className="text-red-500 hover:text-red-700"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
