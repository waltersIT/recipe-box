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

export const IMPORT_METHOD_LABELS: Record<string, string> = {
  manual: 'Typed in',
  url: 'Imported from a link',
  browser: 'Saved from the browser',
  pdf: 'Imported from a PDF',
  image: 'Imported from a screenshot',
}
