import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merge class names, with later Tailwind utilities winning over earlier ones.
 *
 * `clsx` handles conditionals; `twMerge` resolves conflicts, so a component can
 * take a `className` that overrides its own defaults without needing `!important`
 * or a specificity fight.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
