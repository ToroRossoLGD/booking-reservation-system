import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { api, ApiError } from "./api";
import { displayDate } from "./stay-types";
import OccupancyImportHistory from "./OccupancyImportHistory";

export type OccupancyImportResult = {
  ranges: { check_in: string; check_out: string; status: "ready" | "existing" | "conflict" }[];
  ignored: number;
  clipped: number;
  applied: boolean;
  created: number;
};

function snapshot() { return localStorage.getItem("bookica_token") ?? ""; }
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("focus", callback);
  return () => { window.removeEventListener("storage", callback); window.removeEventListener("focus", callback); };
}

export default function OccupancyImport({ propertyId, onImported }: { propertyId: number; onImported: () => void }) {
  const session = useSyncExternalStore(subscribe, snapshot);
  return <ImportPanel key={`${propertyId}:${session}`} propertyId={propertyId} session={session} onImported={onImported} />;
}

function ImportPanel({ propertyId, session, onImported }: { propertyId: number; session: string; onImported: () => void }) {
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<OccupancyImportResult | null>(null);
  const [error, setError] = useState("");
  const [historyVersion, setHistoryVersion] = useState(0);
  const [sourceUrl, setSourceUrl] = useState("");
  const inFlight = useRef(false);
  const live = useRef(true);
  const report = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  useEffect(() => { if (result) report.current?.focus(); }, [result]);
  function current() { return live.current && snapshot() === session; }

  async function selectFile(file?: File) {
    if (inFlight.current) return;
    setResult(null); setContent(""); setError(""); setSourceUrl("");
    if (!file) return;
    if (file.size > 100_000) { setError("Fajl može imati najviše 100 KB."); return; }
    inFlight.current = true; setBusy(true);
    try {
      const text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      if (current()) setContent(text);
    } catch { if (current()) setError("Fajl nije moguće pročitati kao UTF-8 tekst."); }
    finally { inFlight.current = false; if (current()) setBusy(false); }
  }

  async function fetchUrl() {
    if (inFlight.current || !sourceUrl.trim() || !current()) return;
    inFlight.current = true; setBusy(true); setError(""); setContent(""); setResult(null);
    if (fileInput.current) fileInput.current.value = "";
    try {
      const fetched = await api.fetchOccupancyUrl(propertyId, sourceUrl.trim());
      if (!current()) return;
      const preview = await api.importOccupancy(propertyId, fetched.content, false);
      if (!current()) return;
      setContent(fetched.content); setResult(preview); setSourceUrl("");
    } catch (err) {
      if (current()) setError(err instanceof ApiError && err.status === 429 ? err.message
        : err instanceof ApiError && err.status === 503 ? "Uvoz preko linka trenutno nije dostupan. Administrator treba da podesi dozvoljene domene; možeš uvesti .ics fajl."
        : "Kalendar nije preuzet. Proveri HTTPS link i odobreni domen. Podržani su samo celodnevni iCal termini bez ponavljanja, do 100 KB. Možeš pokušati ponovo ili uvesti fajl.");
    } finally { inFlight.current = false; if (current()) setBusy(false); }
  }

  async function submit(apply: boolean) {
    if (inFlight.current || !content || !current()) return;
    inFlight.current = true; setBusy(true); setError("");
    try {
      const next = await api.importOccupancy(propertyId, content, apply);
      if (!current()) return;
      setResult(next);
      if (next.applied) onImported();
    } catch (err) {
      if (current()) setError(err instanceof ApiError && [400, 422].includes(err.status)
        ? "Fajl nije podržan. Koristi iCal 2.0 sa najviše 100 celodnevnih događaja (VALUE=DATE), bez ponavljanja, satnice, DURATION ili dodatnih komponenti."
        : "Uvoz nije potvrđen. Proveri prijavu i ponovi pregled; već sačuvani identični termini neće se duplirati.");
    } finally {
      inFlight.current = false;
      if (current()) {
        setBusy(false);
        if (apply) setHistoryVersion(value => value + 1);
      }
    }
  }

  const conflicts = result?.ranges.some(item => item.status === "conflict");
  const labels = { ready: "Nova blokada", existing: "Već blokirano", conflict: "Preklapanje — proveri termin" };
  return <section aria-label="Uvoz zauzetosti iz kalendara">
    <h4>Uvezi iCal fajl</h4>
    <OccupancyImportHistory propertyId={propertyId} revision={historyVersion} />
    <p>Jednokratni uvoz celodnevnih termina, bez automatskog osvežavanja. Datumi važe za sve oglase istog objekta. Nazivi događaja i podaci gostiju se ne čuvaju.</p>
    <p>Uvoze se samo datumi od danas do 365 dana unapred. Preklopljeni i susedni termini iz fajla se spajaju. Poslednji datum je slobodan za novi dolazak.</p>
    <label>Privatni iCal HTTPS link<input type="password" autoComplete="off" spellCheck={false} maxLength={2048} disabled={busy} value={sourceUrl} onChange={event => { setSourceUrl(event.target.value); setContent(""); setResult(null); setError(""); if (fileInput.current) fileInput.current.value = ""; }} /></label>
    <p>Link mora biti sa domena koji je administrator odobrio. Čuvaj ga kao lozinku. Preuzimanje je jednokratno; potvrda uvozi pregledani snimak, bez ponovnog preuzimanja i automatskog praćenja promena.</p>
    <button disabled={busy || !sourceUrl.trim()} onClick={() => void fetchUrl()}>Preuzmi i pregledaj link</button>
    <label>iCal fajl (.ics, do 100 KB)<input ref={fileInput} type="file" accept=".ics,text/calendar" disabled={busy} onChange={event => void selectFile(event.target.files?.[0])} /></label>
    <button disabled={busy || !content} onClick={() => void submit(false)}>Pregledaj uvoz</button>
    {busy && <p role="status">Obrada kalendara…</p>}
    {error && <p role="alert">{error}</p>}
    {result && <div ref={report} tabIndex={-1} aria-label="Rezultat pregleda kalendara">
      <p>Preskočenih događaja: {result.ignored}. Skraćenih na podržani period: {result.clipped}.</p>
      {result.ranges.length === 0 && <p>Nema zauzetih termina za uvoz u narednih 365 dana.</p>}
      <ul>{result.ranges.map(item => <li key={`${item.check_in}:${item.check_out}`}>{displayDate(item.check_in)} — {displayDate(item.check_out)}: {labels[item.status]}</li>)}</ul>
      {result.applied ? <p role="status">Uvoz je završen. Novih blokada: {result.created}. Uklanjaš ih pojedinačno u listi blokada.</p> : <>
        {conflicts && <p role="alert">Postoje preklapanja sa rezervacijama, pripremom ili blokadama. Nijedan termin nije uvezen. Ispravi fajl ili zauzetost pa ponovi pregled.</p>}
        <p>Potvrdom dodaješ prikazane nove blokade. Postojeće rezervacije i blokade se ne menjaju. Zauzetost se ponovo proverava pri potvrdi.</p>
        <button disabled={busy || conflicts || !result.ranges.length} onClick={() => void submit(true)}>Potvrdi uvoz blokada</button>
      </>}
      <button disabled={busy} onClick={() => { setResult(null); setContent(""); setError(""); if (fileInput.current) { fileInput.current.value = ""; fileInput.current.focus(); } }}>Zatvori pregled</button>
    </div>}
  </section>;
}
