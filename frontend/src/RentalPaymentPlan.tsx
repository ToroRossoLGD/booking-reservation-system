import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { ChargeEvent, RentalAgreement, RentalCharge } from "./rental-agreement-types";
import { displayDate, propertyToday, stayMoney } from "./stay-types";

export default function RentalPaymentPlan({ agreement, owner, token }: { agreement: RentalAgreement; owner: boolean; token: string }) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<RentalCharge[] | null>(null);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<RentalCharge | null>(null);
  const live = useRef(true);
  const working = useRef(false);
  const cancel = useRef<HTMLButtonElement>(null);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  useEffect(() => { if (confirm) cancel.current?.focus(); }, [confirm]);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    api.rentalCharges(agreement.id, controller.signal).then(data => { if (!controller.signal.aborted) setRows(data); }).catch(() => { if (!controller.signal.aborted) setError("Raspored nije učitan. Pokušaj ponovo."); });
    return () => controller.abort();
  }, [agreement.id, open, version]);
  async function record() {
    if (!confirm || working.current || (localStorage.getItem("bookica_token") ?? "") !== token) return;
    working.current = true; setBusy(true); setError("");
    try {
      const next = await api.recordRentalPayment(agreement.id, confirm.id, confirm.version, !confirm.paid);
      if (live.current) { setRows(previous => previous?.map(row => row.id === next.id ? next : row) ?? null); setConfirm(null); }
    } catch { if (live.current) { setConfirm(null); setError("Evidencija nije potvrđena. Osveži raspored i proveri stanje pre novog pokušaja."); } }
    finally { working.current = false; if (live.current) setBusy(false); }
  }
  return <section aria-label={`Raspored za dogovor ${agreement.id}`}>
    <button disabled={busy} aria-expanded={open} onClick={() => { setRows(null); setError(""); setConfirm(null); setOpen(v => !v); }}>Raspored kirija i depozita</button>
    {open && <>
      <p>Uplate evidentira vlasnik ručno. Oznaka ne predstavlja bankarsku potvrdu; novac se ne naplaćuje kroz aplikaciju.</p>
      {!rows && !error && <p role="status">Učitavanje rasporeda…</p>}
      {rows && <p>Bez evidentirane uplate: {stayMoney(rows.filter(r => !r.paid).reduce((total, row) => total + row.amount_cents, 0), agreement.currency)} (uključujući buduće kirije i depozit).</p>}
      <ul className="rental-charge-list">{rows?.map(row => <li key={row.id}><strong>{row.sequence === 0 ? "Depozit" : `Kirija ${row.sequence}`} · {stayMoney(row.amount_cents, agreement.currency)}</strong><p>Dospeće: {displayDate(row.due_date)}. {row.paid ? "Vlasnik je evidentirao uplatu." : row.due_date < propertyToday(agreement.timezone) ? "Rok je prošao; uplata nije evidentirana." : "Uplata nije evidentirana."}</p>
        {owner && <button disabled={busy || !!error} onClick={() => setConfirm(row)}>{row.paid ? "Ispravi oznaku uplate" : "Evidentiraj uplatu"} — {row.sequence === 0 ? "depozit" : `kirija ${row.sequence}`}</button>}
        {confirm?.id === row.id && <fieldset disabled={busy}><legend>{row.paid ? "Ukloniti oznaku uplate? Izmena ostaje u istoriji." : "Potvrdi da je cela stavka uplaćena van aplikacije."}</legend><button onClick={() => void record()}>Potvrdi evidenciju</button><button ref={cancel} onClick={() => setConfirm(null)}>Odustani od evidencije</button></fieldset>}
        <ChargeHistory key={`${row.id}:${row.version}`} agreementId={agreement.id} chargeId={row.id} />
      </li>)}</ul>
      {error && <p role="alert">{error}</p>}
      <button disabled={busy} onClick={() => { setRows(null); setConfirm(null); setError(""); setVersion(v => v + 1); }}>Osveži raspored kirija</button>
    </>}
  </section>;
}

function ChargeHistory({ agreementId, chargeId }: { agreementId: number; chargeId: number }) {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<ChargeEvent[] | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    api.rentalChargeEvents(agreementId, chargeId, controller.signal).then(rows => { if (!controller.signal.aborted) setEvents(rows); }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [agreementId, chargeId, open]);
  return <div><button aria-expanded={open} onClick={() => { setError(false); setEvents(null); setOpen(v => !v); }}>Istorija evidencije</button>{open && (error ? <p role="alert">Istorija nije učitana. Zatvori i ponovo otvori prikaz.</p> : events ? <><p>Poslednjih 20 izmena vlasnika.</p>{!events.length && <p>Nema promena evidencije.</p>}<ul>{events.map(event => <li key={event.id}>{event.paid ? "Uplata evidentirana" : "Oznaka uplate uklonjena"} · {new Intl.DateTimeFormat("sr-Latn-RS", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(new Date(event.created_at))} UTC</li>)}</ul></> : <p role="status">Učitavanje istorije…</p>)}</div>;
}
