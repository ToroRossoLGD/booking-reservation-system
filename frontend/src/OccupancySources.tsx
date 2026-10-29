import { useEffect, useRef, useState } from "react";
import { api } from "./api";

export type OccupancySource = { id: number; name: string; revision: number; last_attempt_at: string | null; last_success_at: string | null; last_status: "applied" | "conflict" | null };

export default function OccupancySources({ propertyId, value, revision, busy, onBusy, onChange, onRemoved }: {
  propertyId: number; value?: number; revision: number; busy: boolean; onBusy: (value: boolean) => void;
  onChange: (value?: number) => void; onRemoved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<OccupancySource[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const live = useRef(true);
  const inFlight = useRef(false);
  const cancel = useRef<HTMLButtonElement>(null);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  useEffect(() => { if (confirm) cancel.current?.focus(); }, [confirm]);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    api.occupancySources(propertyId, controller.signal).then(result => {
      if (!controller.signal.aborted) { setRows(result); setLoading(false); }
    }).catch(() => { if (!controller.signal.aborted) { setError("Izvori nisu učitani. Pokušaj ponovo."); setLoading(false); } });
    return () => controller.abort();
  }, [open, propertyId, revision, version]);
  async function change(remove: boolean) {
    if (inFlight.current || busy || (!remove && !name.trim())) return;
    inFlight.current = true; onBusy(true); setError("");
    try {
      if (remove && value) {
        await api.removeOccupancySource(propertyId, value);
        if (!live.current) return;
        onChange(undefined); onRemoved(); setConfirm(false);
      } else {
        const created = await api.createOccupancySource(propertyId, name.trim());
        if (!live.current) return;
        onChange(created.id); setName("");
      }
      setVersion(current => current + 1);
    } catch { if (live.current) setError("Promena izvora nije potvrđena. Osveži izvore i pokušaj ponovo. Dozvoljeno je najviše 10 izvora po objektu."); }
    finally { inFlight.current = false; if (live.current) onBusy(false); }
  }
  const selected = rows.find(row => row.id === value);
  const timestamp = (value: string | null) => value ? new Intl.DateTimeFormat("sr-Latn-RS", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(new Date(value)) + " UTC" : "Nema zabeleženog uvoza";
  return <section aria-label="Izvori kalendara">
    <button disabled={busy} aria-expanded={open} onClick={() => { if (!open) setLoading(true); setOpen(current => !current); }}>{open ? "Sakrij izvore" : "Uvoz po izvoru kalendara"}</button>
    {value && !open && <p>Izabran je izvor kalendara. Potvrda može ukloniti njegove prethodne blokade.</p>}
    {open && <>
      <p>Izaberi isti izvor pri svakom uvozu njegovog kompletnog kalendara. Blokade tog izvora koje nedostaju u novom snimku uklanjaju se tek nakon potvrde. Link se ne čuva i nema automatskog osvežavanja.</p>
      {loading && <p role="status">Učitavanje izvora…</p>}
      <label>Izvor za ovaj uvoz<select disabled={busy || loading} value={value ?? ""} onChange={event => { onChange(event.target.value ? Number(event.target.value) : undefined); setConfirm(false); }}>
        <option value="">Bez izvora — samo dodaj blokade</option>
        {value && !selected && <option value={value}>Izvor nije dostupan — osveži listu ili izaberi drugi</option>}
        {rows.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select></label>
      {selected && <><p>Poslednji pokušaj: {timestamp(selected.last_attempt_at)}. {selected.last_status === "conflict" ? "Preklapanje: prethodne blokade su sačuvane." : selected.last_status === "applied" ? "Uvoz uspešan." : "Izvor još nije uvezen."}</p><p>Poslednji uspešan uvoz: {timestamp(selected.last_success_at)}.</p></>}
      <label>Naziv novog izvora (bez linka)<input maxLength={80} disabled={busy} value={name} onChange={event => setName(event.target.value)} /></label>
      <button disabled={busy || loading || !name.trim()} onClick={() => void change(false)}>Dodaj izvor</button>
      {value && (confirm ? <fieldset disabled={busy}><legend>Ukloniti izvor i sve njegove aktivne blokade? Rezervacije i ostale blokade ostaju.</legend><button onClick={() => void change(true)}>Potvrdi uklanjanje izvora</button><button ref={cancel} onClick={() => setConfirm(false)}>Odustani od uklanjanja izvora</button></fieldset> : <button disabled={busy} onClick={() => setConfirm(true)}>Ukloni izvor i njegove blokade</button>)}
      <button disabled={busy || loading} onClick={() => { setError(""); setLoading(true); setVersion(current => current + 1); }}>Osveži izvore</button>
      {error && <p role="alert">{error}</p>}
    </>}
  </section>;
}
