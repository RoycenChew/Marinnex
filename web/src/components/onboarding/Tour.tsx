import { useEffect, useLayoutEffect, useState } from 'react'
import { X } from 'lucide-react'
import { VerificationBadge } from '../ui/VerificationBadge'
import { Button } from '../ui/Button'
import { cn } from '../../lib/utils'

/**
 * The five-step tour from Part 6.
 *
 * Two departures from the package.
 *
 * **Step 4 shows no confidence figure.** The package's wording — "Confidence
 * helps you decide which fields need attention" — describes a number this
 * system does not have. The step teaches the vocabulary the workspace actually
 * uses instead, with the real badges, so what a user learns here is what they
 * will see.
 *
 * **Steps 2 to 4 do not point at anything.** They describe the workspace, which
 * a brand-new account has no document to open. Spotlighting an element that is
 * not on screen would mean either faking one or pointing at nothing, so those
 * steps are plain cards and only steps that have a real target get a spotlight.
 *
 * It is never shown unasked. `Welcome` offers it; `hasSeenTour` keeps it from
 * coming back.
 */

export type TourStep = {
  title: string
  body: string
  /** `data-tour` value of the element to spotlight, when one is on screen. */
  anchor?: string
  illustration?: 'verification'
}

const STEPS: TourStep[] = [
  {
    title: 'Start here',
    body: 'Drop an invoice into this area, or choose a file. A PDF, a scan or a photo all work. Sending the same file twice is recognised, so you are never charged for it twice.',
    anchor: 'upload',
  },
  {
    title: 'Your document stays in front of you',
    body: 'Once a document is read, it opens in two halves: the original page on one side, the information found in it on the other. You never have to remember what the invoice said.',
  },
  {
    title: 'Every value points back at the page',
    body: 'Selecting a value highlights the exact words it was read from. If something looks wrong, you can see where it came from without opening the file yourself.',
  },
  {
    title: 'How a value was checked',
    body: 'Rather than a score, each value says how it was verified. These are the states you will see, and anything that is not simply found on the page is held for you to look at.',
    illustration: 'verification',
  },
  {
    title: 'Then use the data',
    body: 'Accept the result, export it as a spreadsheet, or tick the fields you want, save them as a schema and call the API from your own system.',
    anchor: 'nav-schemas',
  },
]

type Rect = { top: number; left: number; width: number; height: number }

export function Tour({ onClose }: { onClose: () => void }) {
  const [index, setIndex] = useState(0)
  const [rect, setRect] = useState<Rect | null>(null)
  const step = STEPS[index]
  const isLast = index === STEPS.length - 1

  // Measure after paint, and again on resize or scroll: the spotlight has to
  // sit on the element, not where the element was when the step opened.
  useLayoutEffect(() => {
    const measure = () => {
      if (!step.anchor) return setRect(null)
      const node = document.querySelector(`[data-tour="${step.anchor}"]`)
      if (!node) return setRect(null)
      const box = node.getBoundingClientRect()
      node.scrollIntoView({ block: 'center', behavior: 'smooth' })
      setRect({ top: box.top, left: box.left, width: box.width, height: box.height })
    }
    measure()
    window.addEventListener('resize', measure)
    window.addEventListener('scroll', measure, true)
    return () => {
      window.removeEventListener('resize', measure)
      window.removeEventListener('scroll', measure, true)
    }
  }, [step.anchor, index])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      if (event.key === 'ArrowRight' && !isLast) setIndex((i) => i + 1)
      if (event.key === 'ArrowLeft' && index > 0) setIndex((i) => i - 1)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose, isLast, index])

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="tour-title"
      className="fixed inset-0 z-50"
    >
      {/* When a step has a target, the dimming comes from the spotlight's own
          outer shadow — a second overlay on top of it would dim the one thing
          the step is pointing at. */}
      <div
        className={cn('absolute inset-0', !rect && 'bg-[var(--color-slate-950)]/50')}
        onClick={onClose}
      />

      {/* The spotlight: a ring around the real element, never a copy of it. */}
      {rect && (
        <div
          aria-hidden
          className="pointer-events-none absolute rounded-[var(--radius-md)] ring-2 ring-[var(--accent-solid)] ring-offset-2 ring-offset-transparent"
          style={{
            top: rect.top - 4,
            left: rect.left - 4,
            width: rect.width + 8,
            height: rect.height + 8,
            boxShadow: '0 0 0 9999px rgba(2,6,23,0.55)',
          }}
        />
      )}

      <div
        className={cn(
          'absolute left-1/2 w-[min(28rem,calc(100vw-2rem))] -translate-x-1/2',
          'rounded-[var(--radius-lg)] border bg-[var(--surface-overlay)] p-5 shadow-lg',
          rect ? 'bottom-10' : 'top-1/2 -translate-y-1/2',
        )}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Skip the tour"
          className="absolute top-3 right-3 rounded-[var(--radius-sm)] p-1 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
        >
          <X className="h-4 w-4" />
        </button>

        <p className="tabular text-xs text-[var(--text-tertiary)]">
          Step {index + 1} of {STEPS.length}
        </p>
        <h2
          id="tour-title"
          className="mt-1 text-base font-semibold text-[var(--text-primary)]"
        >
          {step.title}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
          {step.body}
        </p>

        {step.illustration === 'verification' && (
          <div className="mt-3 flex flex-wrap gap-1.5 rounded-[var(--radius-md)] bg-[var(--surface-sunken)] p-3">
            {(['exact', 'derived', 'fuzzy_ocr', 'not_found', 'not_checked'] as const).map(
              (key) => (
                <VerificationBadge key={key} match={key} />
              ),
            )}
          </div>
        )}

        <div className="mt-5 flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            Skip
          </button>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              onClick={() => setIndex((i) => i - 1)}
              disabled={index === 0}
            >
              Back
            </Button>
            <Button
              variant="primary"
              onClick={() => (isLast ? onClose() : setIndex((i) => i + 1))}
            >
              {isLast ? 'Finish' : 'Next'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
