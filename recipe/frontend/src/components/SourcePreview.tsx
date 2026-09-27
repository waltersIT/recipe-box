import { useState } from 'react'
import { objectUrl } from '../lib/objectUrl'

function isPdf(file: File) {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
}

/** Shows the original PDF/screenshots next to the editor so an import can be checked. */
export default function SourcePreview({ files }: { files: File[] }) {
  const urls = files.map(objectUrl)
  const [broken, setBroken] = useState<Set<number>>(new Set())

  return (
    <div className="source-preview">
      {files.map((file, index) =>
        isPdf(file) ? (
          <iframe key={urls[index]} src={urls[index]} title={file.name} />
        ) : broken.has(index) ? (
          <p key={urls[index]} className="muted small">
            {file.name} can't be previewed in this browser.
          </p>
        ) : (
          <img
            key={urls[index]}
            src={urls[index]}
            alt={file.name}
            onError={() => setBroken((prev) => new Set(prev).add(index))}
          />
        ),
      )}
    </div>
  )
}
