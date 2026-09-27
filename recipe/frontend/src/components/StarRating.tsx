interface Props {
  value: number
  onChange?: (value: number) => void
  size?: 'sm' | 'md'
}

export default function StarRating({ value, onChange, size = 'md' }: Props) {
  const stars = [1, 2, 3, 4, 5]
  if (!onChange) {
    return (
      <span className={`stars stars-${size}`} aria-label={`${value} out of 5 stars`}>
        {stars.map((star) => (
          <span key={star} className={star <= value ? 'star on' : 'star'} aria-hidden="true">
            ★
          </span>
        ))}
      </span>
    )
  }
  return (
    <span className={`stars stars-${size} editable`} role="radiogroup" aria-label="Rating">
      {stars.map((star) => (
        <button
          key={star}
          type="button"
          role="radio"
          aria-checked={star === value}
          aria-label={`${star} star${star > 1 ? 's' : ''}`}
          className={star <= value ? 'star on' : 'star'}
          // Clicking the current rating clears it.
          onClick={() => onChange(star === value ? 0 : star)}
        >
          ★
        </button>
      ))}
    </span>
  )
}
