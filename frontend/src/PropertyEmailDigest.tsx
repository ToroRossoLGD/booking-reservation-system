import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { api } from "./api";

export type EmailDigestStatus = { interval_hours: 1 | 24; next_run_at: string | null; enabled: boolean; available: boolean; verified: boolean; last_status: "unconfigured" | "pending" | "accepted" | "failed" | "unverified"; last_attempt_at: string | null; last_accepted_at: string | null };
const snapshot = () => localStorage.getItem("bookica_token") ?? "";
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback); window.addEventListener("focus", callback);
  return () => { window.removeEventListener("storage", callback); window.removeEventListener("focus", callback); };
}
export default function PropertyEmailDigest() {
  const token = useSyncExternalStore(subscribe, snapshot);
  return <Panel key={token} token={token} />;
}
function Panel({ token }: { token: string }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<EmailDigestStatus | null>(null);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const live = useRef(true);
  const working = useRef(false);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    api.emailDigestStatus(controller.signal).then(value => { if (!controller.signal.aborted) setStatus(value); }).catch(() => { if (!controller.signal.aborted) setError("Podešavanje nije učitano. Pokušaj ponovo."); });
    return () => controller.abort();
  }, [open, version]);
  async function change(enabled: boolean, interval?: 1 | 24) {
    if (!status || working.current || snapshot() !== token) return;
    working.current = true; setBusy(true); setError("");
    try {
      const result = await (interval === undefined ? api.setEmailDigest(enabled) : api.setEmailDigest(enabled, interval));
      if (live.current && snapshot() === token) setStatus(result);
    } catch { if (live.current) setError("Promena nije potvrđena. Osveži status pre novog pokušaja."); }
    finally { working.current = false; if (live.current) setBusy(false); }
  }
  const time = (value: string | null) => value ? new Intl.DateTimeFormat("sr-Latn-RS", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(new Date(value)) + " UTC" : "Nije zabeleženo";
  return <section aria-label="Email sažetak obaveštenja">
    <button className="ph-outline" disabled={busy} aria-expanded={open} onClick={() => { setOpen(value => !value); setStatus(null); setError(""); }}>Email sažetak obaveštenja</button>
    {open && <>
      <p>Uključivanjem dozvoljavaš slanje email sažetka novih obaveštenja o boravcima, najmu i kupovini na verifikovanu adresu svog naloga. Sažetak sadrži broj novih obaveštenja i link ka ovom inboxu, bez privatnih detalja.</p>
      <p>Sažetak se proverava jednom na sat ili jednom dnevno, do 20 obaveštenja po poruci. Promena učestalosti pomera sledeću proveru od trenutka čuvanja i zadržava obaveštenja koja čekaju slanje. Uključivanje počinje od novih obaveštenja; prethodna se ne šalju. Poruka koja je već u obradi može stići nakon isključivanja. Email sažetak nije hitan podsetnik.</p>
      {!status && !error && <p role="status">Učitavanje email podešavanja…</p>}
      {status && <>
        <label>Učestalost email sažetka<select disabled={busy || !!error || (status.enabled && (!status.available || !status.verified))} value={status.interval_hours} onChange={event => void change(status.enabled, Number(event.target.value) as 1 | 24)}><option value={1}>Jednom na sat</option><option value={24}>Jednom dnevno</option></select></label>
        <p>Sledeća planirana provera: {time(status.next_run_at)}. Provera ne garantuje slanje: potrebna su nova obaveštenja i aktivan pozadinski servis. Poruka koja je već u obradi koristi prethodni raspored.</p>
        <p role="status">Email sažetak je {status.enabled ? "uključen" : "isključen"}.</p>
        {!status.available && <p>Email sažetak nije aktiviran na serveru.</p>}
        {!status.verified && <p>Prvo <a href="/verify-email">verifikuj email adresu</a>.</p>}
        {status.last_status === "failed" && <p role="alert">Poslednji pokušaj nije uspeo. Posle tri uzastopna neuspeha slanje se isključuje. Proveri podešavanje sa administratorom.</p>}
        <p>Poslednji pokušaj: {time(status.last_attempt_at)}. Poslednje SMTP prihvatanje: {time(status.last_accepted_at)}.</p>
        <p>SMTP prihvatanje ne potvrđuje prijem ili čitanje. Pri prekidu veze ili restartu moguć je ponovljen sažetak.</p>
        <button disabled={busy || !!error || (!status.enabled && (!status.available || !status.verified))} onClick={() => void change(!status.enabled)}>{status.enabled ? "Isključi email sažetak" : "Uključi email sažetak"}</button>
      </>}
      {error && <p role="alert">{error}</p>}
      <button disabled={busy} onClick={() => { setStatus(null); setError(""); setVersion(value => value + 1); }}>Osveži status email sažetka</button>
    </>}
  </section>;
}
