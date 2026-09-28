export function formatMinutes(minutes: number | null | undefined): string {
  if (!minutes) return ''
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  if (hours && mins) return `${hours} hr ${mins} min`
  if (hours) return `${hours} hr`
  return `${mins} min`
}

export function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export function isHeading(line: string): boolean {
  return line.startsWith('#')
}

export function headingText(line: string): string {
  return line.replace(/^#+\s*/, '')
}

/** Textarea contents -> list items (one per non-empty line). */
export function textToLines(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

export function linesToText(lines: string[]): string {
  return lines.join('\n')
}

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 24 * 60],
  ['month', 30 * 24 * 60],
  ['week', 7 * 24 * 60],
  ['day', 24 * 60],
  ['hour', 60],
  ['minute', 1],
]

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

/** "3 days ago", for comment timestamps. */
export function timeAgo(iso: string): string {
  const minutes = (Date.now() - new Date(iso).getTime()) / 60000
  if (minutes < 1) return 'just now'
  for (const [unit, size] of UNITS) {
    if (minutes >= size) return relative.format(-Math.round(minutes / size), unit)
  }
  return 'just now'
}

export const IMPORT_METHOD_LABELS: Record<string, string> = {
  manual: 'Typed in',
  url: 'Imported from a link',
  browser: 'Saved from the browser',
  pdf: 'Imported from a PDF',
  image: 'Imported from a screenshot',
}
