/**
 * Whether this user has seen the tour.
 *
 * `localStorage` only, and only this flag. It is a UI preference — nothing about
 * a document, a value or a key may be written here, per the project's logging
 * rule. Keyed by user id so two accounts on one machine do not inherit each
 * other's state.
 *
 * Every access is wrapped: in a private window, or with site data blocked, the
 * accessor throws, and a thrown tour flag must not take the page down. A failed
 * read means "not seen", which shows the tour once more rather than hiding it
 * forever.
 */

const PREFIX = 'marinnex.tour.seen.'

export function hasSeenTour(userId: string | undefined): boolean {
  if (!userId) return true
  try {
    return window.localStorage.getItem(PREFIX + userId) === '1'
  } catch {
    return false
  }
}

export function markTourSeen(userId: string | undefined): void {
  if (!userId) return
  try {
    window.localStorage.setItem(PREFIX + userId, '1')
  } catch {
    /* Storage unavailable. The tour simply offers itself again. */
  }
}
