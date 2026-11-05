import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { api } from "./api";
import type { RentalInquiry } from "./rental-types";
import type { AgreementAction, AgreementInput, RentalAgreement } from "./rental-agreement-types";
import { displayDate, stayMoney } from "./stay-types";
import RentalPaymentPlan from "./RentalPaymentPlan";
import RentalTerminationPanel from "./RentalTerminationPanel";
import "./rental-agreements.css";

const snapshot = () => localStorage.getItem("bookica_token") ?? "";
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback); window.addEventListener("focus", callback);
  return () => { window.removeEventListener("storage", callback); window.removeEventListener("focus", callback); };
}
const statuses = { proposed: "Predlog", accepted: "Prihvaćeno", declined: "Odbijeno", withdrawn: "Povučeno" };
export default function RentalAgreements(props: { inquiry: RentalInquiry; owner: boolean }) {
  const token = useSyncExternalStore(subscribe, snapshot);
  return <Panel key={`${props.inquiry.id}:${token}`} {...props} token={token} />;
}

function Panel({ inquiry, owner, token }: { inquiry: RentalInquiry; owner: boolean; token: string }) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<RentalAgreement[] | null>(null);
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<{ row: RentalAgreement; action: AgreementAction } | null>(null);
  const live = useRef(true);
  const working = useRef(false);
  const cancel = useRef<HTMLButtonElement>(null);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  useEffect(() => { if (confirm) cancel.current?.focus(); }, [confirm]);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    api.rentalAgreements(inquiry.id, offset, controller.signal).then(data => { if (!controller.signal.aborted) setRows(data); }).catch(() => { if (!controller.signal.aborted) setError("Dogovori nisu učitani. Pokušaj ponovo."); });
    return () => controller.abort();
  }, [open, inquiry.id, offset, version]);
  function reload(next = offset) { setError(""); setRows(null); setConfirm(null); setOffset(next); setVersion(v => v + 1); }
  async function mutate(input?: AgreementInput) {
    if (working.current || snapshot() !== token) return;
    working.current = true; setBusy(true); setError("");
    try {
      if (input) await api.proposeRentalAgreement(inquiry.id, input);
      else if (confirm) await api.decideRentalAgreement(confirm.row.id, confirm.row.version, confirm.action);
      if (live.current && snapshot() === token) reload(0);
    } catch { if (live.current) { setConfirm(null); setError("Promena nije potvrđena. Proveri verifikaciju email adrese, datume i postojeće dogovore, pa osveži prikaz pre novog pokušaja."); } }
    finally { working.current = false; if (live.current) setBusy(false); }
  }
  const active = !["closed", "withdrawn"].includes(inquiry.status);
  return <section className="rental-agreements" aria-label="Dogovor o dugoročnom najmu">
    <button disabled={busy} aria-expanded={open} onClick={() => { setRows(null); setError(""); setConfirm(null); setOffset(0); setOpen(v => !v); }}>Dogovor o najmu i kirije</button>
    {open && <>
      <p>Predlog i potvrda uslova u aplikaciji služe za zajedničku evidenciju dogovora. Ne stvaraju elektronski potpis niti naplatu. Dogovor ne blokira kalendar rezervacija na dan.</p>
      <p>Prihvatanje pravi mesečni raspored od početnog datuma, uz zaseban depozit. Raniji završetak zahteva predlog vlasnika i potvrdu stanara. Za druge izmene dogovorite se direktno.</p>
      {!rows && !error && <p role="status">Učitavanje dogovora…</p>}
      {rows?.length === 0 && <p>Nema dogovora na ovoj stranici.</p>}
      {rows?.map(row => <div className="rental-agreement-card" key={row.id}>
        <h4>Dogovor #{row.id} · {statuses[row.status]}</h4>
        <p>{displayDate(row.start_date)} — {displayDate(row.end_date)} (krajnji datum nije uključen), {row.months} meseci.</p>
        <p>Mesečna kirija: <strong>{stayMoney(row.monthly_cents, row.currency)}</strong>. Depozit: {stayMoney(row.deposit_cents, row.currency)}.</p>
        <p>Prvobitna ukupna kirija: {stayMoney(row.monthly_cents * row.months, row.currency)}. Depozit se vodi odvojeno; povraćaj depozita nije obuhvaćen.</p>
        {row.terminated_on && <p role="status">Dogovoren raniji završetak: {displayDate(row.terminated_on)} (datum nije uključen). Ukidanje budućih kirija prikazano je u rasporedu.</p>}
        {row.notes && <p className="agreement-note">{row.notes}</p>}
        {row.status === "proposed" && <div><button disabled={busy || !!error} onClick={() => setConfirm({ row, action: owner ? "withdraw" : "accept" })}>{owner ? "Povuci predlog najma" : "Prihvati uslove najma"}</button>{!owner && <button disabled={busy || !!error} onClick={() => setConfirm({ row, action: "decline" })}>Odbij predlog najma</button>}</div>}
        {confirm?.row.id === row.id && <fieldset disabled={busy}><legend>{confirm.action === "accept" ? "Potvrdi prikazane uslove i raspored kirija" : "Potvrdi promenu predloga"}</legend><button onClick={() => void mutate()}>Potvrdi odluku o najmu</button><button ref={cancel} onClick={() => setConfirm(null)}>Odustani od odluke</button></fieldset>}
        {row.status === "accepted" && <><RentalPaymentPlan key={`${row.id}:${row.version}`} agreement={row} owner={owner} token={token} /><RentalTerminationPanel agreement={row} owner={owner} token={token} onAccepted={() => reload()} /></>}
      </div>)}
      {owner && active && offset === 0 && rows && !rows.some(r => ["proposed", "accepted"].includes(r.status)) && <Proposal inquiry={inquiry} disabled={busy || !!error} onSubmit={data => void mutate(data)} />}
      {error && <p role="alert">{error}</p>}
      <button disabled={busy} onClick={() => reload()}>Osveži dogovore</button>
      <nav aria-label="Stranice dogovora"><button disabled={busy || !rows || offset === 0} onClick={() => reload(Math.max(0, offset - 10))}>Prethodnih 10 dogovora</button><button disabled={busy || rows?.length !== 10} onClick={() => reload(offset + 10)}>Sledećih 10 dogovora</button></nav>
    </>}
  </section>;
}

function Proposal({ inquiry, disabled, onSubmit }: { inquiry: RentalInquiry; disabled: boolean; onSubmit: (data: AgreementInput) => void }) {
  const [start, setStart] = useState(inquiry.move_in);
  const [months, setMonths] = useState(String(inquiry.duration_months));
  const [rent, setRent] = useState((inquiry.monthly_price_cents / 100).toFixed(2));
  const [deposit, setDeposit] = useState(((inquiry.deposit_cents ?? 0) / 100).toFixed(2));
  const [notes, setNotes] = useState("");
  const request = useRef(crypto.randomUUID());
  function changed() { request.current = crypto.randomUUID(); }
  function cents(value: string) { const [whole, decimal = ""] = value.replace(",", ".").split("."); return Number(whole) * 100 + Number(decimal.padEnd(2, "0")); }
  return <form onChange={changed} onSubmit={event => { event.preventDefault(); onSubmit({ request_id: request.current, start_date: start, months: Number(months), monthly_cents: cents(rent), deposit_cents: cents(deposit), notes: notes.trim() }); }}>
    <fieldset disabled={disabled}><legend>Novi predlog najma ({inquiry.currency})</legend>
      <label>Početak najma<input type="date" required value={start} onChange={event => setStart(event.target.value)} /></label>
      <label>Trajanje u mesecima<input type="number" min="1" max="120" step="1" required value={months} onChange={event => setMonths(event.target.value)} /></label>
      <label>Mesečna kirija<input inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" maxLength={14} required value={rent} onChange={event => setRent(event.target.value)} /></label>
      <label>Depozit<input inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" maxLength={14} required value={deposit} onChange={event => setDeposit(event.target.value)} /></label>
      <label>Napomene uz dogovor<textarea maxLength={2000} rows={3} value={notes} onChange={event => setNotes(event.target.value)} /></label>
      <p>Svaka kirija dospeva na početku svog meseca najma. Ako datum ne postoji u mesecu, koristi se poslednji dan tog meseca. Režije nisu uključene u ovaj raspored.</p>
      <button type="submit">Pošalji predlog najma</button>
    </fieldset>
  </form>;
}
