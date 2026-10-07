import { useCallback, useRef, useState } from 'react'
import { CheckCircle2, FileUp, Loader2, Upload, XCircle } from 'lucide-react'
import { toast } from 'sonner'
import { API_ORIGIN } from '../api/client'
import { formatBytes } from '../lib/format'
import { problemMessage } from '../lib/status'
import { cn } from '../lib/utils'
import { Button } from './ui/Button'

const ACCEPTED = '.pdf,.png,.jpg,.jpeg,.tif,.tiff'
const MAX_BYTES = 20 * 1024 * 1024

type Upload = {
  id: string
  name: string
  size: number
  state: 'uploading' | 'done' | 'error'
  message?: string
}

/**
 * Drag-and-drop upload with per-file state.
 *
 * Uses `fetch` rather than the typed client because the body is multipart: the
 * browser must set `Content-Type` itself so the boundary is right. Each file
 * gets its own row, because uploading five and being told only that "an upload
 * failed" is not actionable.
 */
export function UploadZone({
  projectId,
  onUploaded,
}: {
  projectId: string | null
  onUploaded: () => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [uploads, setUploads] = useState<Upload[]>([])

  const send = useCallback(
    async (files: File[]) => {
      for (const file of files) {
        const id = crypto.randomUUID()
        setUploads((current) => [
          { id, name: file.name, size: file.size, state: 'uploading' },
          ...current,
        ])

        if (file.size > MAX_BYTES) {
          setUploads((current) =>
            current.map((u) =>
              u.id === id
                ? { ...u, state: 'error', message: 'Over the 20 MB limit' }
                : u,
            ),
          )
          continue
        }

        try {
          const body = new FormData()
          body.append('file', file)
          const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''
          const response = await fetch(`${API_ORIGIN}/v1/documents${query}`, {
            method: 'POST',
            // A fresh key per file, so a retry of *this* upload is idempotent
            // while a different file is never mistaken for it.
            headers: { 'Idempotency-Key': id },
            body,
            credentials: 'include',
          })
          if (!response.ok) {
            const problem = await response.json().catch(() => ({}))
            throw problem
          }
          setUploads((current) =>
            current.map((u) => (u.id === id ? { ...u, state: 'done' } : u)),
          )
          onUploaded()
        } catch (error) {
          const message = problemMessage(error)
          setUploads((current) =>
            current.map((u) =>
              u.id === id ? { ...u, state: 'error', message } : u,
            ),
          )
          toast.error(`${file.name} was not uploaded`, { description: message })
        }
      }
    },
    [projectId, onUploaded],
  )

  const onDrop = (event: React.DragEvent) => {
    event.preventDefault()
    setDragging(false)
    const files = Array.from(event.dataTransfer.files)
    if (files.length) void send(files)
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click()
        }}
        role="button"
        tabIndex={0}
        aria-label="Upload documents"
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center gap-1 rounded-[var(--radius-lg)]',
          'border border-dashed px-6 py-8 text-center transition-colors duration-150',
          dragging
            ? 'border-[var(--accent-solid)] bg-[var(--accent-subtle)]'
            : 'bg-[var(--surface-raised)] hover:border-[var(--border-strong)]',
        )}
      >
        <FileUp
          className={cn(
            'h-5 w-5',
            dragging ? 'text-[var(--text-brand)]' : 'text-[var(--text-tertiary)]',
          )}
        />
        <p className="text-sm font-medium text-[var(--text-primary)]">
          Drop invoices here, or click to choose
        </p>
        <p className="text-xs text-[var(--text-tertiary)]">
          PDF, PNG, JPEG or TIFF, up to 20 MB each
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED}
          className="hidden"
          onChange={(e) => {
            const files = Array.from(e.target.files ?? [])
            if (files.length) void send(files)
            e.target.value = ''
          }}
        />
      </div>

      {uploads.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1">
          {uploads.slice(0, 5).map((upload) => (
            <li
              key={upload.id}
              className="flex items-center gap-2 rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-3 py-1.5 text-sm"
            >
              {upload.state === 'uploading' && (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--text-tertiary)]" />
              )}
              {upload.state === 'done' && (
                <CheckCircle2 className="h-3.5 w-3.5 text-[var(--color-success-600)]" />
              )}
              {upload.state === 'error' && (
                <XCircle className="h-3.5 w-3.5 text-[var(--color-danger-600)]" />
              )}
              <span className="min-w-0 flex-1 truncate text-[var(--text-primary)]">
                {upload.name}
              </span>
              <span className="tabular shrink-0 text-xs text-[var(--text-tertiary)]">
                {upload.state === 'error' ? upload.message : formatBytes(upload.size)}
              </span>
              {upload.state === 'error' && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    setUploads((current) =>
                      current.filter((u) => u.id !== upload.id),
                    )
                  }
                >
                  Dismiss
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
