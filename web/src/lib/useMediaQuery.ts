import { useEffect, useState } from 'react'

/**
 * Subscribe to a media query.
 *
 * Used for layout decisions a CSS breakpoint cannot make — the workspace at
 * 768 px and below becomes two tabs rather than two panes, which means
 * rendering different components, not restyling the same ones.
 *
 * The initial value is read synchronously so the first paint is already
 * correct, rather than mounting the desktop split view and swapping it out.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(
    () => window.matchMedia?.(query).matches ?? false,
  )

  useEffect(() => {
    const list = window.matchMedia(query)
    const update = () => setMatches(list.matches)
    update()
    list.addEventListener('change', update)
    return () => list.removeEventListener('change', update)
  }, [query])

  return matches
}
