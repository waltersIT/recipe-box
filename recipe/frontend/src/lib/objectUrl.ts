const urls = new WeakMap<Blob, string>()

/**
 * A stable blob: URL for previewing a local file.
 *
 * URLs are cached per file rather than created and revoked in an effect, which
 * breaks under React's StrictMode (the effect cleanup revokes a URL that's
 * still on screen). They're freed when the page unloads; the files here are a
 * handful of screenshots the user picked, so that's fine.
 */
export function objectUrl(file: Blob): string {
  let url = urls.get(file)
  if (!url) {
    url = URL.createObjectURL(file)
    urls.set(file, url)
  }
  return url
}
