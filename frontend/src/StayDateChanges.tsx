import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import NightlyPriceBreakdown from "./NightlyPriceBreakdown";
import StayTimes from "./StayTimes";
import type { Stay, StayChangePage, StayQuote } from "./stay-types";
import { displayDate, propertyToday, shiftDate, stayMoney } from "./stay-types";

const labels = { pending: "Čeka vlasnika", accepted: "Odobreno", declined: "Odbijeno", withdrawn: "Povučeno", expired: "Više nije aktivno" };

export default function StayDateChanges({ stay, owner, onChanged }: { stay: Stay; owner: boolean; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  return <section className="stay-changes" aria-label={`Promene termina rezervacije ${stay.id}`}>
    <button className="ph-outline" aria-expanded={open} onClick={() => setOpen(value => !value)}>Promene termina</button>
    {open && <ChangePanel key={`${stay.check_in}:${stay.check_out}:${stay.status}`} stay={stay} owner={owner} onChanged={onChanged} />}
  </section>;
}

function ChangePanel({ stay, owner, onChanged }: { stay: Stay; owner: boolean; onChanged: () => void }) {
  const [page, setPage] = useState<StayChangePage | null>(null);
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [arrival, setArrival] = useState(stay.check_in);
  const [departure, setDeparture] = useState(stay.check_out);
  const [quote, setQuote] = useState<StayQuote | null>(null);
  const [consent, setConsent] = useState(false);
  const requestId = useRef("");
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    const controller = new AbortController();
    api.stayChanges(stay.id, offset, controller.signal).then(result => {
      if (!controller.signal.aborted) { setPage(result); setLoading(false); }
    }).catch(() => { if (!controller.signal.aborted) { setError("Zahtevi nisu učitani. Osveži istoriju i pokušaj ponovo."); setLoading(false); } });
    return () => controller.abort();
  }, [stay.id, offset, version]);
  function refresh(nextOffset = 0) { setLoading(true); setError(""); setOffset(nextOffset); setVersion(value => value + 1); }
  function invalidate() { setQuote(null); setConsent(false); setError(""); setMessage(""); }
  async function check() {
    if (busy) return;
    setBusy(true); invalidate();
    try {
      const result = await api.stayChangeQuote(stay.id, { check_in: arrival, check_out: departure, guests: stay.guests });
      if (mounted.current) { requestId.current = crypto.randomUUID(); setQuote(result); }
    } catch { if (mounted.current) setError("Novi termin nije dostupan ili ne ispunjava aktuelna pravila boravka. Proveri datume i pokušaj ponovo."); }
    finally { if (mounted.current) setBusy(false); }
  }
  async function send() {
    if (!quote || !consent || busy) return;
    setBusy(true); setError("");
    try {
      const result = await api.requestStayChange(stay.id, { check_in: arrival, check_out: departure, guests: stay.guests, quote, request_id: requestId.current });
      if (mounted.current) {
        setQuote(null); setConsent(false);
        setMessage(result.status === "pending" ? "Zahtev je poslat. Dosadašnji termin ostaje potvrđen do odobrenja vlasnika." : `Status zahteva: ${labels[result.status]}.`);
        refresh();
        if (result.status !== "pending") onChanged();
      }
    } catch (err) {
      if (mounted.current) {
        if (err instanceof ApiError && [400, 404, 409, 422].includes(err.status)) { setQuote(null); setConsent(false); setError("Stanje rezervacije, dostupnost ili cena su se promenili. Osveži istoriju i ponovo proveri termin."); }
        else setError("Potvrda nije stigla. Pokušaj ponovo; isti zahtev neće biti dupliran.");
      }
    } finally { if (mounted.current) setBusy(false); }
  }
  async function decide(id: number, action: "accept" | "decline" | "withdraw") {
    if (busy) return;
    setBusy(true); setError("");
    try {
      await api.decideStayChange(stay.id, id, action);
      if (mounted.current) { refresh(); onChanged(); }
    } catch { if (mounted.current) setError("Izmena nije potvrđena. Ako su se cena ili dostupnost promenili, gost treba da povuče zahtev i pošalje novi. Osveži pregled pre ponovnog pokušaja."); }
    finally { if (mounted.current) setBusy(false); }
  }
  const eligible = stay.status === "confirmed" && stay.check_in > propertyToday(stay.timezone);
  const pending = page?.items.some(item => item.status === "pending");
  return <div>
    <p>Broj gostiju ostaje isti. Zahtev ne čuva novi termin: dosadašnja rezervacija važi dok vlasnik ne odobri promenu. Nova cena se računa po aktuelnim uslovima, uz plaćanje kod domaćina.</p>
    <button className="ph-outline" disabled={busy || loading} onClick={() => refresh()}>Osveži istoriju promena</button>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {loading ? <p role="status">Učitavanje zahteva…</p> : page && <>
      {!page.items.length && <p>Nema zahteva za promenu termina.</p>}
      {page.items.map(item => <div className="stay-change-item" key={item.id}>
        <h3>Zahtev #{item.id} · {labels[item.status]}</h3>
        <p>Pre promene: {displayDate(item.original.check_in)} — {displayDate(item.original.check_out)} · {stayMoney(item.original.total_cents, item.original.currency)}</p>
        <p>Predlog: {displayDate(item.check_in)} — {displayDate(item.check_out)} · <strong>{stayMoney(item.quote.total_cents, item.quote.currency)}</strong></p>
        <StayTimes {...item.quote} /><NightlyPriceBreakdown prices={item.quote.nightly_prices} currency={item.quote.currency} />
        {item.status === "pending" && eligible && <div className="stay-change-actions">{owner ? <><button className="ph-outline" disabled={busy} onClick={() => decide(item.id, "accept")}>Odobri termin i cenu</button><button className="ph-outline" disabled={busy} onClick={() => decide(item.id, "decline")}>Odbij zahtev</button></> : <button className="ph-outline" disabled={busy} onClick={() => decide(item.id, "withdraw")}>Povuci zahtev</button>}</div>}
      </div>)}
      {(offset > 0 || page.has_next) && <nav aria-label="Stranice promena termina"><button className="ph-outline" disabled={busy || offset === 0} onClick={() => refresh(Math.max(0, offset - 20))}>Noviji zahtevi</button><button className="ph-outline" disabled={busy || !page.has_next} onClick={() => refresh(offset + 20)}>Stariji zahtevi</button></nav>}
      {!owner && eligible && !pending && offset === 0 && <form onSubmit={event => { event.preventDefault(); void check(); }}>
        <fieldset disabled={busy}><legend>Predloži novi termin</legend>
          <label>Novi dolazak<input type="date" required min={shiftDate(propertyToday(stay.timezone), 1)} value={arrival} onChange={event => { setArrival(event.target.value); invalidate(); }} /></label>
          <label>Novi odlazak<input type="date" required min={arrival ? shiftDate(arrival, 1) : undefined} value={departure} onChange={event => { setDeparture(event.target.value); invalidate(); }} /></label>
          <button className="ph-outline" type="submit">Proveri novi termin i cenu</button>
        </fieldset>
        {quote && <div className="stay-quote"><p>Dosadašnja cena: {stayMoney(stay.total_cents, stay.currency)}</p><strong>Nova cena: {stayMoney(quote.total_cents, quote.currency)}</strong><StayTimes {...quote} /><NightlyPriceBreakdown prices={quote.nightly_prices} currency={quote.currency} />
          <label><input type="checkbox" disabled={busy} checked={consent} onChange={event => setConsent(event.target.checked)} />Prihvatam novu cenu i uslove ako vlasnik odobri promenu.</label>
          <button className="ph-primary" type="button" disabled={busy || !consent} onClick={send}>Pošalji zahtev za promenu</button>
        </div>}
      </form>}
    </>}
  </div>;
}
