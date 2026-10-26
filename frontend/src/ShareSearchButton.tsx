import { useEffect, useId, useRef, useState } from "react";

export default function ShareSearchButton({ path }: { path: string }) {
  const [status, setStatus] = useState<"copied" | "manual" | null>(null);
  const manualInput = useRef<HTMLInputElement>(null);
  const hintId = useId();
  useEffect(() => { if (status === "manual") manualInput.current?.focus(); }, [status]);
  const url = `${window.location.origin}${path}`;
  async function copy() {
    setStatus(null);
    try { await navigator.clipboard.writeText(url); setStatus("copied"); }
    catch { setStatus("manual"); manualInput.current?.focus(); }
  }
  return <div className="ph-share-search">
    <button type="button" className="ph-outline" onClick={() => void copy()}>Kopiraj link pretrage</button>
    {status === "copied" && <p role="status">Link pretrage je kopiran.</p>}
    {status === "manual" && <><p id={hintId} role="alert">Kopiranje nije uspelo. Link je označen za ručno kopiranje.</p><label>Kopiraj link pretrage ručno<input ref={manualInput} aria-describedby={hintId} readOnly value={url} onFocus={event => event.target.select()} /></label></>}
  </div>;
}
