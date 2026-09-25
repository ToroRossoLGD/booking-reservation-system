import { useState } from "react";

export default function ShareSearchButton({ path }: { path: string }) {
  const [status, setStatus] = useState<"copied" | "manual" | null>(null);
  const url = `${window.location.origin}${path}`;
  async function copy() {
    setStatus(null);
    try { await navigator.clipboard.writeText(url); setStatus("copied"); }
    catch { setStatus("manual"); }
  }
  return <div className="ph-share-search">
    <button type="button" className="ph-outline" onClick={() => void copy()}>Kopiraj link pretrage</button>
    {status === "copied" && <p role="status">Link pretrage je kopiran.</p>}
    {status === "manual" && <label>Kopiraj link pretrage ručno<input readOnly value={url} onFocus={event => event.target.select()} /></label>}
  </div>;
}
