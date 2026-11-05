import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { AgreementAction, RentalAgreement, RentalCharge, RentalTermination, TerminationInput } from "./rental-agreement-types";
import { displayDate, propertyToday, stayMoney } from "./stay-types";

const labels = { proposed: "Čeka odluku", accepted: "Prihvaćen", declined: "Odbijen", withdrawn: "Povučen" };
type Confirmation = { input: TerminationInput } | { row: RentalTermination; action: AgreementAction };

export default function RentalTerminationPanel({ agreement, owner, token, onAccepted }: { agreement: RentalAgreement; owner: boolean; token: string; onAccepted: () => void }) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<RentalTermination[] | null>(null);
  const [charges, setCharges] = useState<RentalCharge[]>([]);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [end, setEnd] = useState("");
  const [notes, setNotes] = useState("");
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const request = useRef(crypto.randomUUID());
  const working = useRef(false);
  const live = useRef(true);
  const cancel = useRef<HTMLButtonElement>(null);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  useEffect(() => { if (confirmation) cancel.current?.focus(); }, [confirmation]);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    Promise.all([api.rentalTerminations(agreement.id, offset, controller.signal), api.rentalCharges(agreement.id, controller.signal)])
      .then(([history, plan]) => { if (!controller.signal.aborted) { setRows(history); setCharges(plan); } })
      .catch(() => { if (!controller.signal.aborted) setError("Podaci nisu učitani. Osveži završetak najma."); });
    return () => controller.abort();
  }, [agreement.id, open, offset, refresh]);
  const affected = (date: string) => charges.filter(c => c.sequence > 0 && c.due_date >= date && !c.voided_at);
  const dates = charges.filter(c => c.sequence > 1 && c.due_date >= propertyToday(agreement.timezone) && !c.voided_at && !affected(c.due_date).some(row => row.paid));
  function reload(next = offset) { setError(""); setRows(null); setCharges([]); setConfirmation(null); setOffset(next); setRefresh(v => v + 1); }
  async function submit() {
    if (!confirmation || working.current || (localStorage.getItem("bookica_token") ?? "") !== token) return;
    working.current = true; setBusy(true); setError("");
    try {
      if ("input" in confirmation) await api.proposeRentalTermination(agreement.id, confirmation.input);
      else await api.decideRentalTermination(agreement.id, confirmation.row.id, confirmation.row.version, confirmation.action);
      if (live.current && (localStorage.getItem("bookica_token") ?? "") === token) {
        if ("action" in confirmation && confirmation.action === "accept") onAccepted();
        else { setEnd(""); setNotes(""); request.current = crypto.randomUUID(); reload(0); }
      }
    } catch { if (live.current) { setConfirmation(null); setError("Promena nije potvrđena. Proveri uplate, datum i verifikaciju naloga. Osveži završetak najma pre novog pokušaja."); } }
    finally { working.current = false; if (live.current) setBusy(false); }
  }
  function consequences(date: string) {
    const items = affected(date);
    return <p>Od {displayDate(date)} (datum nije uključen) ukida se {items.length} stavki kirije, ukupno {stayMoney(items.reduce((sum, c) => sum + c.amount_cents, 0), agreement.currency)}. Ranije kirije i depozit ostaju u evidenciji. Nema automatskog povraćaja novca.</p>;
  }
  return <section aria-label={`Završetak dogovora ${agreement.id}`}>
    <button disabled={busy} aria-expanded={open} onClick={() => { reload(0); setOpen(v => !v); }}>Prevremeni završetak najma</button>
    {open && <>
      <p>Vlasnik predlaže, stanar potvrđuje. Sam predlog ne menja najam. Završetak je moguć na početku narednog mesečnog perioda, pre prvobitnog kraja. Već evidentirane buduće uplate blokiraju potvrdu. Ovo ne menja kalendar noćenja.</p>
      {!rows && !error && <p role="status">Učitavanje predloga završetka…</p>}
      {rows?.length === 0 && <p>Nema predloga završetka na ovoj stranici.</p>}
      {rows?.map(row => <article key={row.id} className="rental-agreement-card">
        <h5>Završetak #{row.id} · {labels[row.status]}</h5>
        <p>Predloženi kraj: {displayDate(row.end_date)}.</p><p className="agreement-note">{row.notes}</p>
        <p>Predloženo: {new Date(row.created_at).toISOString()} {row.decided_at && `· Odluka: ${new Date(row.decided_at).toISOString()}`}</p>
        {row.status === "proposed" && <>
          {consequences(row.end_date)}
          <button disabled={busy || !!error || !!confirmation} onClick={() => setConfirmation({ row, action: owner ? "withdraw" : "accept" })}>{owner ? "Povuci predlog završetka" : "Prihvati raniji završetak"}</button>
          {!owner && <button disabled={busy || !!error || !!confirmation} onClick={() => setConfirmation({ row, action: "decline" })}>Odbij raniji završetak</button>}
        </>}
      </article>)}
      {owner && rows && offset === 0 && !agreement.terminated_on && !rows.some(row => ["accepted", "proposed"].includes(row.status)) && <form onSubmit={event => { event.preventDefault(); if (dates.some(c => c.due_date === end) && notes.trim()) setConfirmation({ input: { request_id: request.current, version: agreement.version, end_date: end, notes: notes.trim() } }); }}>
        <fieldset disabled={busy || !!error || !!confirmation}><legend>Predloži raniji završetak</legend>
          {!dates.length ? <p>Nema dostupnog mesečnog datuma bez budućih evidentiranih uplata.</p> : <>
            <label>Novi datum završetka<select required value={end} onChange={event => { setEnd(event.target.value); request.current = crypto.randomUUID(); }}><option value="">Izaberi datum</option>{dates.map(c => <option key={c.id} value={c.due_date}>{displayDate(c.due_date)}</option>)}</select></label>
            <label>Razlog i dogovorene napomene<textarea required maxLength={2000} value={notes} onChange={event => { setNotes(event.target.value); request.current = crypto.randomUUID(); }} /></label>
            {end && consequences(end)}<button type="submit">Pregledaj predlog završetka</button>
          </>}
        </fieldset>
      </form>}
      {confirmation && <fieldset disabled={busy}><legend>{"input" in confirmation ? "Potvrdi slanje predloga stanaru" : confirmation.action === "accept" ? "Potvrdi raniji kraj i ukidanje navedenih kirija" : "Potvrdi odluku o predlogu"}</legend>
        {("input" in confirmation || confirmation.action === "accept") && consequences("input" in confirmation ? confirmation.input.end_date : confirmation.row.end_date)}
        <button onClick={() => void submit()}>Potvrdi odluku o završetku</button><button ref={cancel} onClick={() => setConfirmation(null)}>Odustani od ove odluke</button>
      </fieldset>}
      {error && <p role="alert">{error}</p>}
      <button disabled={busy} onClick={() => reload()}>Osveži završetak najma</button>
      <nav aria-label="Istorija završetka"><button disabled={busy || !rows || offset === 0} onClick={() => reload(Math.max(0, offset - 10))}>Noviji predlozi završetka</button><button disabled={busy || rows?.length !== 10} onClick={() => reload(offset + 10)}>Stariji predlozi završetka</button></nav>
    </>}
  </section>;
}
