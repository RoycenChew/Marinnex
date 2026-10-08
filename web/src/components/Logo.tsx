import MarinnexLogo from '../assets/marinnex-logo.svg?react'
import MarinnexMark from '../assets/marinnex-mark.svg?react'
import { cn } from '../lib/utils'

/**
 * The Marinnex Lab logo.
 *
 * Inlined through svgr rather than loaded with `<img src>`, because an `<img>`
 * renders the SVG as an isolated document where `currentColor` resolves to
 * black. Inlined, the mark inherits the surrounding text colour and follows the
 * theme without a second asset.
 *
 * Both files are interim traces of `assets/logo.png`; see their headers.
 */

export function Logo({
  variant = 'full',
  className,
}: {
  /** `full` is the mark plus the wordmark; `mark` is the hexagon alone. */
  variant?: 'full' | 'mark'
  className?: string
}) {
  const Svg = variant === 'mark' ? MarinnexMark : MarinnexLogo
  return (
    <Svg
      className={cn(
        'text-[var(--text-brand)]',
        variant === 'mark' ? 'h-7 w-auto' : 'h-7 w-auto',
        className,
      )}
      aria-label="Marinnex Lab"
    />
  )
}
