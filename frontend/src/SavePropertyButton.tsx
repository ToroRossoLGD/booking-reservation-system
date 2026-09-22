import { useRef, useState } from "react";
import { api, ApiError } from "./api";
import "./saved-properties.css";

export default function SavePropertyButton({ propertyId, title, saved, onChange }: { propertyId: number; title: string; saved: boolean | null; onChange: (saved: boolean) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [login, setLogin] = useState(false);
  const inFlight = useRef(false);

  async function toggle() {
    if (inFlight.current || saved === null) return;
    setError(""); setLogin(false);
    if (!localStorage.getItem("bookica_token")) { setLogin(true); setError("Prijavi se da sačuvaš oglas."); return; }
    inFlight.current = true; setBusy(true);
    try {
      if (saved) await api.unsaveProperty(propertyId); else await api.saveProperty(propertyId);
      onChange(!saved);
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      setLogin(status === 401);
      setError(status === 401 ? "Prijava je istekla. Prijavi se ponovo." : status === 404 ? "Oglas više nije dostupan." : "Izmena nije sačuvana. Pokušaj ponovo.");
    } finally { inFlight.current = false; setBusy(false); }
  }
  return <div className="property-save">
    <button type="button" className="property-save-button" aria-pressed={saved ?? false} aria-label={`${saved ? "Ukloni iz sačuvanih" : "Sačuvaj oglas"}: ${title}`} disabled={busy || saved === null} onClick={() => void toggle()}>
      <span aria-hidden="true">{saved ? "♥" : "♡"}</span> {busy ? "Čuvanje…" : saved === null ? "Provera…" : saved ? "Sačuvano" : "Sačuvaj oglas"}
    </button>
    {error && <p role="alert">{error} {login && <a href="/account">Prijavi se</a>}</p>}
  </div>;
}
