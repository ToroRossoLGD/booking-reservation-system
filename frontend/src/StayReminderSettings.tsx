import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { api } from "./api";
import ReminderHistory from "./ReminderHistory";

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback); window.addEventListener("focus", callback);
  return () => { window.removeEventListener("storage", callback); window.removeEventListener("focus", callback); };
}
const snapshot = () => localStorage.getItem("bookica_token") ?? "";

export default function StayReminderSettings({ viewing = false }: { viewing?: boolean }) {
  const token = useSyncExternalStore(subscribe, snapshot);
  return <Settings key={`${token}:${viewing}`} token={token} viewing={viewing} />;
}

function Settings({ token, viewing }: { token: string; viewing: boolean }) {
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const live = useRef(true);
  const saving = useRef(false);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    (viewing ? api.viewingReminderPreferences : api.stayReminderPreferences)(controller.signal).then(value => { if (!controller.signal.aborted) setEnabled(value.enabled); })
      .catch(() => { if (!controller.signal.aborted) setError("Podešavanje nije učitano. Pokušaj ponovo."); });
    return () => controller.abort();
  }, [open, version, viewing]);
  async function save() {
    if (saving.current || enabled === null || snapshot() !== token) return;
    saving.current = true; setBusy(true); setError(""); setMessage("");
    try {
      const next = await (viewing ? api.setViewingReminderPreferences : api.setStayReminderPreferences)(!enabled);
      if (live.current && snapshot() === token) { setEnabled(next.enabled); setMessage("Podešavanje je sačuvano."); }
    } catch { if (live.current && snapshot() === token) setError("Promena nije potvrđena. Osveži podešavanje pre novog pokušaja."); }
    finally { saving.current = false; if (live.current) setBusy(false); }
  }
  return <section aria-label={viewing ? "Podsetnici za razgledanja" : "Podsetnici za boravke"}>
    <button className="ph-outline" disabled={busy} aria-expanded={open} onClick={() => { setEnabled(null); setError(""); setMessage(""); setOpen(value => !value); }}>{viewing ? "Podsetnici za razgledanja" : "Podsetnici za dolazak i odlazak"}</button>
    {open && <div>
      <p>{viewing ? "Podsetnik u aplikaciji stiže u poslednja 24 sata pre potvrđenog razgledanja, kada je pozadinski servis aktivan. Podešavanje važi za sve tvoje upite za najam i kupovinu, kao i razgledanja tvojih stanova." : "Podsetnik u aplikaciji stiže dan pre dolaska i odlaska, od 09:00 po vremenskoj zoni smeštaja, kada je pozadinski servis aktivan. Podešavanje važi za sve tvoje boravke i rezervacije tvojih stanova."}</p>
      <p>Email i push se ne šalju. Ostala obaveštenja ostaju uključena. Isključivanje ne uklanja već poslata obaveštenja; podsetnik koji je već u obradi može još stići.</p>
      {enabled === null && !error && <p role="status">Učitavanje podešavanja…</p>}
      {enabled !== null && <><p role="status">Podsetnici su {enabled ? "uključeni" : "isključeni"}.</p><button className="ph-outline" disabled={busy || !!error} onClick={() => void save()}>{enabled ? "Isključi podsetnike" : "Uključi podsetnike"}</button></>}
      {message && <p role="status">{message}</p>}
      {error && <div role="alert"><p>{error}</p><button disabled={busy} onClick={() => { setError(""); setEnabled(null); setVersion(value => value + 1); }}>Osveži podešavanje</button></div>}
      <ReminderHistory viewing={viewing} />
    </div>}
  </section>;
}
