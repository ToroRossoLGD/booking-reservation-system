import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { PropertyListing } from "./property-types";
import type { StayBlockPage } from "./stay-types";
import { displayDate, propertyToday, shiftDate } from "./stay-types";

export default function StayBlockManager({ property }: { property: PropertyListing }) {
  const today = propertyToday(property.timezone);
  const [start, setStart] = useState(today);
  const [end, setEnd] = useState(shiftDate(today, 1));
  const [reason, setReason] = useState("");
  const [page, setPage] = useState<StayBlockPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [confirm, setConfirm] = useState<number | null>(null);
  const inFlight = useRef(false);
  const request = useRef<{ body: string; id: string } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    api.stayBlocks(property.id, offset, controller.signal).then(result => {
      if (!controller.signal.aborted) { setPage(result); setLoading(false); }
    }).catch(() => { if (!controller.signal.aborted) { setLoading(false); setError("Blokade nisu učitane. Proveri prijavu i pokušaj ponovo."); } });
    return () => controller.abort();
  }, [property.id, offset, version]);
  function refresh(next = offset) { setLoading(true); setError(""); setOffset(next); setVersion(value => value + 1); }
  async function create() {
    if (inFlight.current) return;
    if (end <= start) { setError("Kraj blokade mora biti posle početka."); return; }
    const data = { check_in: start, check_out: end, reason: reason.trim() };
    const body = JSON.stringify(data);
    if (request.current?.body !== body) request.current = { body, id: crypto.randomUUID() };
    inFlight.current = true; setBusy(true); setError(""); setMessage("");
    try {
      await api.createStayBlock(property.id, { ...data, request_id: request.current.id });
      request.current = null; setReason(""); setMessage("Termin je blokiran."); refresh(0);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 409 ? "Termin se preklapa sa rezervacijom ili blokadom, ili je zahtev već iskorišćen. Osveži blokade i proveri rezervacije." : err instanceof ApiError && [400, 422].includes(err.status) ? "Proveri datume: od danas do najviše godinu dana unapred." : "Blokada nije sačuvana. Pokušaj ponovo.");
    } finally { inFlight.current = false; setBusy(false); }
  }
  async function remove(id: number) {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(""); setMessage("");
    try {
      await api.removeStayBlock(property.id, id); setConfirm(null); setMessage("Blokada je uklonjena.");
      refresh(page?.items.length === 1 && offset > 0 ? offset - 20 : offset);
    } catch { setError("Uklanjanje nije uspelo. Pokušaj ponovo."); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return <section className="ph-property-form" aria-label={`Blokade: ${property.title}`}>
    <h3>Zauzetost: {property.title}</h3>
    <p>Blokade važe za sve oglase istog objekta. Poslednji datum nije blokiran i može biti novi dolazak. Razlog vidiš samo ti i administratori.</p>
    <p>Vremenska zona: {property.timezone ?? "Europe/Belgrade"}. Postojeće rezervacije se ne otkazuju blokadom.</p>
    {property.offer_type === "short_stay" && <form onSubmit={event => { event.preventDefault(); void create(); }}>
      <fieldset disabled={busy}>
        <label>Početak blokade<input type="date" required min={today} max={shiftDate(today, 364)} value={start} onChange={event => setStart(event.target.value)} /></label>
        <label>Kraj blokade<input type="date" required min={start ? shiftDate(start, 1) : today} max={shiftDate(today, 365)} value={end} onChange={event => setEnd(event.target.value)} /></label>
        <label className="ph-form-wide">Privatni razlog (opciono)<input maxLength={300} value={reason} onChange={event => setReason(event.target.value)} /></label>
      </fieldset>
      <button className="ph-primary" disabled={busy}>Blokiraj termin</button>
    </form>}
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {loading ? <p role="status">Učitavanje blokada…</p> : page && <>
      <p>Aktivnih blokada: {page.total}</p>
      {page.items.map(block => <div className="ph-owner-listing" key={block.id}><p>{displayDate(block.check_in)} — {displayDate(block.check_out)}<br />{block.reason || "Bez napomene"}</p>{confirm === block.id ? <div><p>Ukloniti ovu blokadu?</p><button disabled={busy} onClick={() => void remove(block.id)}>Potvrdi uklanjanje</button><button disabled={busy} onClick={() => setConfirm(null)}>Odustani</button></div> : <button disabled={busy} onClick={() => setConfirm(block.id)}>Ukloni blokadu</button>}</div>)}
    </>}
    <div className="ph-pagination"><button disabled={busy || loading || offset === 0} onClick={() => refresh(offset - 20)}>Prethodne blokade</button><button disabled={busy || loading} onClick={() => refresh()}>Osveži blokade</button><button disabled={busy || loading || !page?.has_next} onClick={() => refresh(offset + 20)}>Sledeće blokade</button></div>
  </section>;
}
