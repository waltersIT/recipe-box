/** Scale the leading quantity of an ingredient line ("1 1/2 cups flour" x2 -> "3 cups flour"). */

const UNICODE_FRACTIONS: Record<string, number> = {
  '½': 1 / 2, '⅓': 1 / 3, '⅔': 2 / 3, '¼': 1 / 4, '¾': 3 / 4,
  '⅛': 1 / 8, '⅜': 3 / 8, '⅝': 5 / 8, '⅞': 7 / 8,
}
const FRACTION_CHARS = Object.keys(UNICODE_FRACTIONS).join('')

const NUMBER = String.raw`(?:\d+\s+\d+\/\d+|\d+\/\d+|\d+(?:\.\d+)?\s*[${FRACTION_CHARS}]|\d+(?:\.\d+)?|[${FRACTION_CHARS}])`
const LEADING = new RegExp(String.raw`^(${NUMBER})(\s*(?:-|–|to)\s*(${NUMBER}))?`)
const METRIC_IN_PARENS = /\((\d+(?:\.\d+)?)(\s*)(g|grams?|kg|ml|l|oz|ounces?)\b/gi

const NICE_FRACTIONS: [number, string][] = [
  [1 / 8, '⅛'], [1 / 4, '¼'], [1 / 3, '⅓'], [3 / 8, '⅜'], [1 / 2, '½'],
  [5 / 8, '⅝'], [2 / 3, '⅔'], [3 / 4, '¾'], [7 / 8, '⅞'],
]

function parseNumber(text: string): number {
  let total = 0
  let rest = text.trim()
  for (const [char, value] of Object.entries(UNICODE_FRACTIONS)) {
    if (rest.includes(char)) {
      total += value
      rest = rest.replace(char, '').trim()
    }
  }
  for (const part of rest.split(/\s+/).filter(Boolean)) {
    if (part.includes('/')) {
      const [num, den] = part.split('/').map(Number)
      if (den) total += num / den
    } else {
      total += Number(part)
    }
  }
  return total
}

function formatNumber(value: number): string {
  const whole = Math.floor(value + 1e-9)
  const fraction = value - whole
  if (fraction < 0.04) return String(whole)
  if (fraction > 0.96) return String(whole + 1)
  for (const [target, char] of NICE_FRACTIONS) {
    if (Math.abs(fraction - target) < 0.04) return whole ? `${whole}${char}` : char
  }
  return String(Math.round(value * 100) / 100)
}

// Units that change form between one and many ("1 cup" / "2 cups").
const PLURALS: Record<string, string> = {
  cup: 'cups', tablespoon: 'tablespoons', teaspoon: 'teaspoons', pound: 'pounds', ounce: 'ounces',
  clove: 'cloves', can: 'cans', stick: 'sticks', slice: 'slices', pinch: 'pinches', sprig: 'sprigs',
  egg: 'eggs', package: 'packages', bunch: 'bunches', quart: 'quarts', pint: 'pints', head: 'heads',
}
const SINGULARS = Object.fromEntries(Object.entries(PLURALS).map(([one, many]) => [many, one]))

function agreeWithQuantity(rest: string, plural: boolean): string {
  // Look at the first word, skipping a size word ("2 large eggs").
  return rest.replace(/^(\s+(?:large|medium|small|whole)?\s*)([a-z]+)\b/i, (whole, before: string, word: string) => {
    const lower = word.toLowerCase()
    const swapped = plural ? PLURALS[lower] : SINGULARS[lower]
    if (!swapped) return whole
    return before + (word[0] === word[0].toUpperCase() ? swapped[0].toUpperCase() + swapped.slice(1) : swapped)
  })
}

function formatAmount(value: number): string {
  return value >= 10 ? String(Math.round(value)) : String(Math.round(value * 10) / 10)
}

export function scaleIngredient(line: string, factor: number): string {
  if (factor === 1 || line.startsWith('#')) return line
  const match = line.match(LEADING)
  if (!match) return line
  const low = parseNumber(match[1]) * factor
  const high = match[3] ? parseNumber(match[3]) * factor : null
  let rest = line.slice(match[0].length)
  // "2 cups (240g) flour": the grams scale too. "1 (14 oz) can" is a can size, so it doesn't.
  if (!/^\s*\(/.test(rest)) {
    rest = rest.replace(METRIC_IN_PARENS, (_, amount: string, space: string, unit: string) =>
      `(${formatAmount(Number(amount) * factor)}${space}${unit}`,
    )
  }
  const original = parseNumber(match[3] ?? match[1])
  const scaled = high ?? low
  if (original <= 1 && scaled > 1) rest = agreeWithQuantity(rest, true)
  else if (original > 1 && scaled <= 1) rest = agreeWithQuantity(rest, false)
  return `${formatNumber(low)}${high !== null ? `–${formatNumber(high)}` : ''}${rest}`
}
