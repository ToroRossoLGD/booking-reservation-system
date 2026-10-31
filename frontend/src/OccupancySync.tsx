import { useEffect, useRef, useState } from "react";
import { api } from "./api";

export type CalendarSyncStatus = {
  available: boolean; configured: boolean; enabled: boolean; allow_empty: boolean; running: boolean; overdue?: boolean;
  next_run_at: string | null; last_attempt_at: string | null; last_success_at: string | null;
  last_status: "unconfigured" | "pending" | "applied" | "conflict" | "superseded" | "inactive" | "fetch_error" | "key_error" | "blocked_empty";
};
type Action = "connect" | "pause" | "resume" | "refresh" | "disconnect";

export default function OccupancySync(props: { propertyId: number; sourceId: number; busy: boolean; onBusy: (value: boolean) => void; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  return <section aria-label="Automatsko osvežavanje kalendara">
    <button disabled={props.busy} aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? "Sakrij automatsko osvežavanje" : "Podesi automatsko osvežavanje"}</button>
    {open && <SyncPanel {...props} />}
  </section>;
}

function SyncPanel({ propertyId, sourceId, busy, onBusy, onChanged }: { propertyId: number; sourceId: number; busy: boolean; onBusy: (value: boolean) => void; onChanged: () => void }) {
  const [status, setStatus] = useState<CalendarSyncStatus | null>(null);
  const [url, setUrl] = useState("");
  const [empty, setEmpty] = useState(false);
  const [confirm, setConfirm] = useState<"connect" | "disconnect" | null>(null);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const live = useRef(true);
  const working = useRef(false);
  const generation = useRef(0);
  const cancel = useRef<HTMLButtonElement>(null);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  useEffect(() => { if (confirm) cancel.current?.focus(); }, [confirm]);
  useEffect(() => {
    const controller = new AbortController();
    let reading = false;
    async function load() {
      if (reading || working.current) return;
      reading = true;
      const current = generation.current;
      try {
        const next = await api.occupancySyncStatus(propertyId, sourceId, controller.signal);
        if (!controller.signal.aborted && current === generation.current) { setStatus(next); setError(""); }
      } catch { if (!controller.signal.aborted && current === generation.current) setError("Status nije učitan. Pokušaj ponovo."); }
      finally { reading = false; }
    }
    void load();
    const timer = window.setInterval(() => void load(), 30_000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [propertyId, sourceId, version]);
  async function change(action: Action) {
    if (working.current || busy) return;
    working.current = true; generation.current++; onBusy(true); setError(""); setMessage("");
    try {
      const next = await api.configureOccupancySync(propertyId, sourceId, action, action === "connect" ? url.trim() : undefined, empty);
      if (!live.current) return;
      setStatus(next); setConfirm(null); setUrl(""); onChanged();
      setMessage(action === "refresh" ? "Osvežavanje je zakazano. Sačekaj izvršavanje pozadinskog zadatka." : "Podešavanje je sačuvano.");
    } catch { if (live.current) setError("Promena nije potvrđena. Proveri odobreni HTTPS domen i serversko podešavanje, pa osveži status pre ponovnog pokušaja."); }
    finally { working.current = false; if (live.current) onBusy(false); }
  }
  const labels: Record<CalendarSyncStatus["last_status"], string> = {
    unconfigured: "Izvor nije povezan.", pending: "Čeka prvo osvežavanje.", applied: "Poslednje automatsko osvežavanje je uspelo.",
    conflict: "Preklapanje: prethodne blokade su sačuvane. Proveri rezervacije i uradi ručni pregled.",
    superseded: "Izvor je promenjen tokom preuzimanja. Zakazan je novi pokušaj.",
    inactive: "Izvor ili vlasnik je promenjen. Ponovo poveži kalendar.",
    fetch_error: "Preuzimanje ili format kalendara nije uspešan. Prethodne blokade su sačuvane.",
    key_error: "Sačuvani link nije moguće otvoriti. Obrati se administratoru ili ponovo poveži kalendar.",
    blocked_empty: "Prazan snimak bi uklonio sve blokade izvora. Blokade su sačuvane; potreban je ručni pregled.",
  };
  const time = (value: string | null) => value ? new Intl.DateTimeFormat("sr-Latn-RS", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(new Date(value)) + " UTC" : "Još nije zabeleženo";
  return <div>
    <p>Uključivanjem dozvoljavaš automatsko dodavanje i uklanjanje blokada ovog izvora približno jednom na sat. Koristi link kompletnog kalendara. Rezervacije i blokade drugih izvora se ne menjaju.</p>
    {!status && !error && <p role="status">Učitavanje automatskog osvežavanja…</p>}
    {status && <>
      {!status.available && <p>Automatsko osvežavanje trenutno nije uključeno na serveru.</p>}
      {status.overdue && <p role="alert">Planirano osvežavanje kasni više od 15 minuta. Proveri pozadinski servis sa administratorom; poslednji uspeh ne garantuje trenutnu zauzetost.</p>}
      <p role="status">{status.configured ? status.enabled ? "Automatika je uključena." : "Automatika je pauzirana." : "Automatika nije podešena."} {status.running && "Preuzimanje je u toku."} {labels[status.last_status]}</p>
      <p>Poslednji pokušaj: {time(status.last_attempt_at)}. Poslednji uspeh: {time(status.last_success_at)}. Sledeći planirani pokušaj: {time(status.next_run_at)}.</p>
      <p>Zakazano vreme ne garantuje izvršavanje: pozadinski servis mora biti aktivan. Prikaz se proverava svakih 30 sekundi dok je ovaj panel otvoren. Listu blokada osveži nakon završenog uvoza.</p>
      {status.configured && <>
        <button disabled={busy || (!status.enabled && !status.available)} onClick={() => void change(status.enabled ? "pause" : "resume")}>{status.enabled ? "Pauziraj automatiku" : "Nastavi automatiku"}</button>
        <button disabled={busy || !status.available || !status.enabled || status.running} onClick={() => void change("refresh")}>Zakaži osvežavanje sada</button>
        <button disabled={busy} onClick={() => setConfirm("disconnect")}>Ukloni sačuvani link</button>
        <p>{status.allow_empty ? "Prazan kalendar sme automatski ukloniti sve blokade izvora." : "Prazan kalendar ne sme automatski ukloniti sve blokade izvora."}</p>
      </>}
      <label>HTTPS link za automatsko osvežavanje<input type="password" autoComplete="off" maxLength={2048} disabled={busy} value={url} onChange={event => { setUrl(event.target.value); setConfirm(null); }} /></label>
      <label><input type="checkbox" checked={empty} disabled={busy} onChange={event => { setEmpty(event.target.checked); setConfirm(null); }} />Dozvoli praznom kalendaru da ukloni sve blokade ovog izvora</label>
      <p>Link se čuva šifrovano na serveru i ne prikazuje se ponovo. Zamena linka ponovo uključuje automatiku.</p>
      <button disabled={busy || !status.available || !url.trim()} onClick={() => setConfirm("connect")}>Poveži i uključi automatiku</button>
      {confirm && <fieldset disabled={busy}><legend>{confirm === "connect" ? `Dozvoliti automatske izmene ovog izvora? ${empty ? "Prazan kalendar može ukloniti sve njegove blokade." : "Prazan kalendar neće ukloniti sve njegove blokade bez ručnog pregleda."}` : "Ukloniti sačuvani link i zaustaviti osvežavanje? Postojeće blokade ostaju."}</legend><button onClick={() => void change(confirm)}>Potvrdi podešavanje automatike</button><button ref={cancel} onClick={() => setConfirm(null)}>Odustani od podešavanja</button></fieldset>}
    </>}
    <button disabled={busy} onClick={() => { setError(""); setVersion(value => value + 1); }}>Osveži status automatike</button>
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
  </div>;
}
