import { useEffect, useRef } from 'react'

/**
 * A bookmark that sends the page you're looking at to Recipe Box.
 *
 * It runs in your own browser tab, so it works on sites that block the
 * server's importer, and on pages you're signed in to. It strips scripts
 * (keeping the JSON-LD recipe data), opens /capture, and hands over the
 * HTML with postMessage once that window says it's ready.
 */
function bookmarkletSource(origin: string): string {
  const code = `(function(){
var o=${JSON.stringify(origin)};
var d=document.documentElement.cloneNode(true);
d.querySelectorAll('script:not([type="application/ld+json"]),style,noscript,svg,iframe,video,audio,canvas,template,link:not([rel="canonical"])').forEach(function(n){n.remove()});
var p={type:"recipebox-capture",url:location.href,html:"<!DOCTYPE html>"+d.outerHTML};
var w=window.open(o+"/capture","_blank");
if(!w){alert("Recipe Box: allow pop-ups for this site, then try again.");return}
function m(e){if(e.origin===o&&e.data==="recipebox-ready"){w.postMessage(p,o);window.removeEventListener("message",m)}}
window.addEventListener("message",m)})();`
  return 'javascript:' + encodeURIComponent(code.replace(/\n/g, ''))
}

export default function Bookmarklet() {
  const link = useRef<HTMLAnchorElement>(null)

  useEffect(() => {
    // React refuses to render javascript: URLs, so set it on the element directly.
    link.current?.setAttribute('href', bookmarkletSource(window.location.origin))
  }, [])

  return (
    <a
      ref={link}
      className="bookmarklet"
      onClick={(event) => {
        event.preventDefault()
        alert('Drag this button to your bookmarks bar, then click it while viewing a recipe.')
      }}
    >
      + Save to Recipe Box
    </a>
  )
}
