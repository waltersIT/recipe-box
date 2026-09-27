import type { ImportResult } from './types'

/**
 * Hands an import result from the import page to the editor.
 *
 * The parsed draft is also kept in sessionStorage so a page refresh doesn't
 * lose it; the original files (File objects) only live in memory.
 */
export interface PendingImport {
  result: ImportResult
  files: File[]
}

const KEY = 'recipebox.pendingImport'
let pending: PendingImport | null = null

export function setPendingImport(value: PendingImport) {
  pending = value
  try {
    sessionStorage.setItem(KEY, JSON.stringify(value.result))
  } catch {
    // Storage can be unavailable (private mode); the in-memory copy still works.
  }
}

export function getPendingImport(): PendingImport | null {
  if (pending) return pending
  try {
    const stored = sessionStorage.getItem(KEY)
    if (stored) return { result: JSON.parse(stored) as ImportResult, files: [] }
  } catch {
    // Ignore unreadable storage.
  }
  return null
}

export function clearPendingImport() {
  pending = null
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // Ignore.
  }
}
