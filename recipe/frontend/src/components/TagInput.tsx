import { useId, useState } from 'react'

interface Props {
  value: string[]
  onChange: (tags: string[]) => void
  suggestions: string[]
}

export default function TagInput({ value, onChange, suggestions }: Props) {
  const [text, setText] = useState('')
  const listId = useId()

  function add(raw: string) {
    const name = raw.replace(/,/g, ' ').trim().replace(/\s+/g, ' ')
    if (name && !value.some((tag) => tag.toLowerCase() === name.toLowerCase())) {
      onChange([...value, name])
    }
    setText('')
  }

  return (
    <div className="tag-input">
      {value.map((tag) => (
        <span key={tag} className="chip">
          {tag}
          <button type="button" aria-label={`Remove ${tag}`} onClick={() => onChange(value.filter((t) => t !== tag))}>
            ×
          </button>
        </span>
      ))}
      <input
        id="tags"
        list={listId}
        value={text}
        placeholder={value.length ? '' : 'Dinner, Vegetarian…'}
        onChange={(event) => {
          const next = event.target.value
          // Picking a datalist suggestion replaces the whole value in one go.
          if (suggestions.includes(next)) add(next)
          else setText(next)
        }}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ',') {
            event.preventDefault()
            add(text)
          } else if (event.key === 'Backspace' && !text && value.length) {
            onChange(value.slice(0, -1))
          }
        }}
        onBlur={() => text && add(text)}
      />
      <datalist id={listId}>
        {suggestions
          .filter((s) => !value.some((tag) => tag.toLowerCase() === s.toLowerCase()))
          .map((s) => (
            <option key={s} value={s} />
          ))}
      </datalist>
    </div>
  )
}
