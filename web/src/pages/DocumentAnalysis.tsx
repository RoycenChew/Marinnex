// @ts-nocheck
import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';
import clsx from 'clsx';
import { AlertCircle, Check, Loader2, Save } from 'lucide-react';

export default function DocumentAnalysis() {
  const { id } = useParams<{ id: string }>();
  const { activeProjectId } = useAuth();
  const queryClient = useQueryClient();

  const [activePage, setActivePage] = useState(1);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [rejectReason, setRejectReason] = useState('');

  const { data: docInfo, isLoading: docLoading } = useQuery({
    queryKey: ['document', id, activeProjectId],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/v1/documents/{document_id}', {
        params: { path: { document_id: id! }, query: { project_id: activeProjectId || undefined } }
      });
      if (error) throw error;
      return data;
    },
    refetchInterval: (data) => data?.status === 'processing' ? 2000 : false
  });

  const { data: analysis } = useQuery({
    queryKey: ['analysis', id, activeProjectId],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/v1/documents/{document_id}/analysis', {
        params: { path: { document_id: id! }, query: { project_id: activeProjectId || undefined } }
      });
      if (error) throw error;
      return data;
    },
    enabled: docInfo?.status !== 'processing',
  });

  const correctionsMutation = useMutation({
    mutationFn: async (changes: { path: string, value: string }[]) => {
      const { data, error } = await apiClient.POST('/v1/extractions/{extraction_id}/corrections', {
        params: { path: { extraction_id: analysis?.extraction_id || '' } },
        body: { changes, reason: 'User correction' }
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      setEditMode(false);
      setEdits({});
      queryClient.invalidateQueries({ queryKey: ['analysis', id] });
    }
  });

  const decisionMutation = useMutation({
    mutationFn: async (decision: { action: 'approve' | 'reject', reason?: string }) => {
      const { data, error } = await apiClient.POST('/v1/extractions/{extraction_id}/decision', {
        params: { path: { extraction_id: analysis?.extraction_id || '' } },
        body: decision
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      setRejectReason('');
      queryClient.invalidateQueries({ queryKey: ['document', id] });
      queryClient.invalidateQueries({ queryKey: ['analysis', id] });
    }
  });

  const handleSaveCorrections = () => {
    const changes = Object.entries(edits).map(([path, value]) => ({ path, value }));
    if (changes.length > 0) {
      correctionsMutation.mutate(changes);
    } else {
      setEditMode(false);
    }
  };

  if (docLoading || (docInfo?.status === 'processing')) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center text-gray-500">
          <Loader2 className="w-8 h-8 animate-spin mb-4" />
          <p>Processing document...</p>
        </div>
      </div>
    );
  }

  if (docInfo?.status === 'document_type_mismatch' || docInfo?.status === 'unsupported' || docInfo?.status === 'failed') {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-md flex items-start gap-3">
          <AlertCircle className="w-5 h-5 mt-0.5 shrink-0" />
          <div>
            <h3 className="font-medium">Cannot process document</h3>
            <p className="text-sm mt-1">Status: {docInfo.status}</p>
            {docInfo.error_code && <p className="text-sm">Error: {docInfo.error_code}</p>}
          </div>
        </div>
      </div>
    );
  }

  if (!analysis) return null;

  const isNeedsReview = analysis.status === 'needs_review';
  const scale = 2.0833; // 150 DPI / 72

  return (
    <div className="flex flex-col h-full gap-4">
      <div className="flex items-center justify-between bg-white p-4 rounded-lg shadow-sm border border-gray-200">
        <div>
          <h1 className="text-lg font-bold text-gray-900">{docInfo?.filename}</h1>
          <p className="text-sm text-gray-500">Version {analysis.version} • {analysis.status}</p>
        </div>
        <div className="flex gap-2">
          {editMode ? (
            <>
              <button 
                onClick={() => setEditMode(false)}
                className="px-3 py-1.5 border border-gray-300 text-gray-700 rounded text-sm hover:bg-gray-50"
              >
                Cancel
              </button>
              <button 
                onClick={handleSaveCorrections}
                disabled={correctionsMutation.isPending}
                className="px-3 py-1.5 bg-primary-dark text-white rounded text-sm flex items-center gap-1 hover:bg-primary-light"
              >
                {correctionsMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Save
              </button>
            </>
          ) : (
            <button 
              onClick={() => setEditMode(true)}
              disabled={analysis.status === 'rejected'}
              className="px-3 py-1.5 border border-gray-300 text-gray-700 rounded text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              Edit
            </button>
          )}
          
          {!editMode && analysis.status !== 'rejected' && analysis.status !== 'completed' && (
            <>
              <button 
                onClick={() => decisionMutation.mutate({ action: 'reject', reason: rejectReason || 'Manual rejection' })}
                disabled={decisionMutation.isPending}
                className="px-3 py-1.5 border border-red-300 text-red-700 rounded text-sm hover:bg-red-50 flex items-center gap-1"
              >
                Reject
              </button>
              <button 
                onClick={() => decisionMutation.mutate({ action: 'approve' })}
                disabled={decisionMutation.isPending}
                className="px-3 py-1.5 bg-green-600 text-white rounded text-sm flex items-center gap-1 hover:bg-green-700"
              >
                <Check className="w-4 h-4" />
                Approve
              </button>
            </>
          )}
        </div>
      </div>

      {isNeedsReview && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 p-3 rounded-md flex items-start gap-2 text-sm">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <div>
            <span className="font-medium">Needs Review: </span>
            {analysis.reasons?.join(', ')}
            {analysis.reasons?.includes('scanned_document_review') && (
               <div className="mt-1 font-medium text-amber-900">Scanned documents are reviewed by a person before acceptance.</div>
            )}
          </div>
        </div>
      )}

      <div className="flex flex-1 gap-4 overflow-hidden">
        {/* Left: Document Viewer */}
        <div className="w-1/2 bg-gray-200 rounded-lg overflow-auto relative flex flex-col items-center p-4">
          <div className="relative inline-block bg-white shadow-md">
            <img 
              src={`${import.meta.env.VITE_API_BASE || 'http://localhost:8000/v1'}/documents/${id}/pages/${activePage}/image`} 
              alt="Document Page" 
              className="block"
              crossOrigin="use-credentials"
            />
            {/* Draw BBoxes */}
            {Object.entries(analysis.fields || {}).map(([path, field]: [string, any]) => {
              if (field.status === 'missing' || field.match === 'not_checked') return null;
              
              return (field.evidence || []).map((ev: any, idx: number) => {
                if (ev.page !== activePage) return null;
                const [x0, y0, x1, y1] = ev.bbox;
                const isSelected = selectedPath === path;
                return (
                  <div 
                    key={`${path}-${idx}`}
                    onClick={() => setSelectedPath(path)}
                    className={clsx(
                      "absolute border cursor-pointer transition-colors",
                      isSelected ? "border-primary-dark bg-primary-light/20 z-10" : "border-yellow-400 bg-yellow-400/20 hover:bg-yellow-400/40"
                    )}
                    style={{
                      left: x0 * scale,
                      top: y0 * scale,
                      width: (x1 - x0) * scale,
                      height: (y1 - y0) * scale
                    }}
                  />
                );
              });
            })}
          </div>
        </div>

        {/* Right: Data Fields */}
        <div className="w-1/2 bg-white rounded-lg shadow-sm border border-gray-200 overflow-y-auto p-4 flex flex-col gap-6">
          
          <div>
             <h3 className="font-semibold text-gray-900 mb-3 border-b pb-2">Extracted Fields</h3>
             <div className="grid grid-cols-2 gap-4">
                {Object.entries(analysis.fields || {}).filter(([path]) => !path.startsWith('line_items')).map(([path, field]: [string, any]) => {
                   const val = edits[path] !== undefined ? edits[path] : field.value;
                   const isMissing = field.status === 'missing';
                   return (
                     <div 
                        key={path} 
                        className={clsx("p-2 rounded border transition-colors cursor-pointer", selectedPath === path ? "border-primary-dark bg-primary-light/5" : "border-gray-100 hover:border-gray-300")}
                        onClick={() => setSelectedPath(path)}
                     >
                        <div className="text-xs text-gray-500 mb-1 font-medium uppercase tracking-wider">{path}</div>
                        {editMode ? (
                           <input 
                              type="text" 
                              value={val || ''}
                              onChange={(e) => setEdits({ ...edits, [path]: e.target.value })}
                              className="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-primary-dark"
                           />
                        ) : (
                           <div className={clsx("text-sm font-medium", isMissing && "text-gray-400 italic")}>
                              {isMissing ? 'Not on document' : (val || '-')}
                           </div>
                        )}
                        <div className="mt-1 flex items-center gap-1">
                           <span className={clsx(
                              "text-[10px] px-1.5 py-0.5 rounded font-medium",
                              field.match === 'exact' ? "bg-green-100 text-green-800" :
                              field.match === 'derived' ? "bg-blue-100 text-blue-800" :
                              field.match === 'fuzzy_ocr' ? "bg-amber-100 text-amber-800" :
                              field.match === 'not_found' ? "bg-red-100 text-red-800" : "bg-gray-100 text-gray-600"
                           )}>
                              {field.match}
                           </span>
                           {field.status === 'needs_review' && <AlertCircle className="w-3 h-3 text-amber-500" />}
                        </div>
                     </div>
                   );
                })}
             </div>
          </div>

        </div>
      </div>
    </div>
  );
}
