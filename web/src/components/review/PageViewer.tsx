import { useEffect, useMemo, useRef, useState } from 'react'
import { Loader2, Maximize2, Minus, Plus } from 'lucide-react'
import { pageImageUrl } from '../../api/queries'
import type { Evidence, FieldEntry } from '../../api/types'
import { matchMeta } from '../../lib/status'
import { cn } from '../../lib/utils'
import { Button } from '../ui/Button'

export type Box = {
  path: string
  page: number
  /** `[x0, y0, x1, y1]` in PDF points. Typed as a list because that is what the
   *  API declares; anything that is not four numbers is skipped when drawing. */
  bbox: number[]
  match: string
}

/** Every field's evidence, flattened into drawable boxes. */
export function boxesOf(fields: Record<string, FieldEntry>): Box[] {
  const out: Box[] = []
  for (const [path, entry] of Object.entries(fields)) {
    for (const item of entry.evidence as Evidence[]) {
      if (item.bbox && item.bbox.length === 4) {
        out.push({ path, page: item.page, bbox: item.bbox, match: entry.match })
      }
    }
  }
  return out
}

type Zoom = 'fit' | 1 | 1.5

/**
 * The page image with evidence boxes drawn over it.
 *
 * The scale rule is the contract's, and getting it wrong moves every box:
 * coordinates are PDF points, origin top-left, y down, and the image is rendered
 * at 150 DPI, so the factor is `renderedWidth / pageWidthInPoints`. Measuring the
 * rendered element rather than assuming 150/72 means the boxes stay correct at
 * any zoom and in any container.
 *
 * The image is fetched with `credentials: "include"` rather than set as an
 * `<img src>`, because a cross-origin `<img>` does not send the session cookie
 * and the request would 401 in development.
 */
export function PageViewer({
  documentId,
  projectId,
  pageCount,
  pageSizes,
  boxes,
  selectedPath,
  onSelectPath,
}: {
  documentId: string
  projectId: string | null
  pageCount: number
  pageSizes: Record<string, number[]>
  boxes: Box[]
  selectedPath: string | null
  onSelectPath: (path: string) => void
}) {
  const [requestedPage, setPage] = useState(1)
  const [zoom, setZoom] = useState<Zoom>('fit')
  const [src, setSrc] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const imageRef = useRef<HTMLImageElement>(null)
  const [rendered, setRendered] = useState({ width: 0, height: 0 })

  /*
   * Follow the selection onto its page, so clicking a field in the right-hand
   * panel never leaves the user looking at the wrong page.
   *
   * Derived during render rather than set from an effect: an effect would render
   * the old page first and then correct it, which shows as a flash of the wrong
   * page every time the selection crosses a page boundary.
   */
  const selectedPage = selectedPath
    ? boxes.find((b) => b.path === selectedPath)?.page
    : undefined
  const page = selectedPage ?? requestedPage

  useEffect(() => {
    let revoked: string | null = null
    let cancelled = false
    setLoading(true)
    setFailed(false)
    fetch(pageImageUrl(documentId, page, projectId), { credentials: 'include' })
      .then(async (response) => {
        if (!response.ok) throw new Error(String(response.status))
        // Rebuild the Blob with an explicit type. `response.blob()` can come
        // back with an empty type through a service worker, and an <img> cannot
        // render an untyped SVG -- binary formats are sniffed, SVG is not.
        const buffer = await response.arrayBuffer()
        const type = response.headers.get('Content-Type') || 'image/png'
        return new Blob([buffer], { type })
      })
      .then((blob) => {
        if (cancelled) return
        revoked = URL.createObjectURL(blob)
        setSrc(revoked)
      })
      .catch(() => !cancelled && setFailed(true))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
      if (revoked) URL.revokeObjectURL(revoked)
    }
  }, [documentId, page, projectId])

  // Re-measure on resize: the split view is draggable, so the image width
  // changes without any state here changing.
  useEffect(() => {
    const element = imageRef.current
    if (!element) return
    const observer = new ResizeObserver(() =>
      setRendered({ width: element.clientWidth, height: element.clientHeight }),
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [src])

  const pageWidth = pageSizes[String(page)]?.[0] ?? 595
  const scale = rendered.width ? rendered.width / pageWidth : 0
  const pageBoxes = useMemo(() => boxes.filter((b) => b.page === page), [boxes, page])

  return (
    <div className="flex h-full flex-col bg-[var(--surface-sunken)]">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b bg-[var(--surface-raised)] px-3 py-2">
        <div className="flex items-center gap-1">
          {Array.from({ length: pageCount }, (_, i) => i + 1).map((n) => (
            <button
              key={n}
              onClick={() => setPage(n)}
              aria-current={n === page}
              className={cn(
                'tabular h-7 min-w-7 rounded-[var(--radius-sm)] px-2 text-xs font-medium',
                n === page
                  ? 'bg-[var(--surface-selected)] text-[var(--text-brand)]'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
              )}
            >
              {n}
            </button>
          ))}
          <span className="ml-1 text-xs text-[var(--text-tertiary)]">
            {pageCount === 1 ? '1 page' : `${pageCount} pages`}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            size="icon"
            variant="ghost"
            aria-label="Fit to width"
            onClick={() => setZoom('fit')}
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            aria-label="Zoom out"
            onClick={() => setZoom(zoom === 1.5 ? 1 : 'fit')}
          >
            <Minus className="h-3.5 w-3.5" />
          </Button>
          <span className="tabular w-10 text-center text-xs text-[var(--text-secondary)]">
            {zoom === 'fit' ? 'Fit' : `${zoom * 100}%`}
          </span>
          <Button
            size="icon"
            variant="ghost"
            aria-label="Zoom in"
            onClick={() => setZoom(zoom === 'fit' ? 1 : 1.5)}
          >
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        {loading && (
          <div className="flex h-full items-center justify-center text-[var(--text-tertiary)]">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        )}
        {failed && !loading && (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-[var(--text-secondary)]">
            This page could not be rendered. The original file is still available
            to download.
          </div>
        )}
        {src && !failed && (
          <div
            className={cn(
              'relative mx-auto',
              zoom === 'fit' ? 'w-full' : 'w-auto',
            )}
            style={zoom === 'fit' ? undefined : { width: `${pageWidth * zoom}px` }}
          >
            <img
              ref={imageRef}
              src={src}
              alt={`Page ${page}`}
              onLoad={(e) =>
                setRendered({
                  width: e.currentTarget.clientWidth,
                  height: e.currentTarget.clientHeight,
                })
              }
              className="block w-full rounded-[var(--radius-sm)] border bg-white shadow-sm"
            />
            {scale > 0 &&
              pageBoxes.map((box, index) => {
                const [x0, y0, x1, y1] = box.bbox as [number, number, number, number]
                const active = box.path === selectedPath
                const colour = matchMeta(box.match).swatch
                return (
                  <button
                    key={`${box.path}-${index}`}
                    onClick={() => onSelectPath(box.path)}
                    aria-label={`Evidence for ${box.path}`}
                    className={cn(
                      'absolute rounded-[2px] transition-[box-shadow,background-color] duration-150',
                      active ? 'z-10' : 'z-0',
                    )}
                    style={{
                      left: x0 * scale,
                      top: y0 * scale,
                      width: Math.max((x1 - x0) * scale, 2),
                      height: Math.max((y1 - y0) * scale, 2),
                      // A tint plus a border: a solid fill would hide the very
                      // text the box is evidence for.
                      backgroundColor: active
                        ? `color-mix(in srgb, ${colour} 28%, transparent)`
                        : `color-mix(in srgb, ${colour} 12%, transparent)`,
                      boxShadow: active
                        ? `0 0 0 2px ${colour}`
                        : `0 0 0 1px color-mix(in srgb, ${colour} 55%, transparent)`,
                    }}
                  />
                )
              })}
          </div>
        )}
      </div>
    </div>
  )
}
