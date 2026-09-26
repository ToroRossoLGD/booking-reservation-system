import StayTimes from "./StayTimes";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { PropertyListing } from "./property-types";
import type { Stay, StayCalendar, StayQuote, StayDates } from "./stay-types";
import { displayDate, propertyToday, shiftDate, stayMoney } from "./stay-types";
import "./stays.css";

export default function StayBooking({ property, initialDates }: { property: PropertyListing; initialDates?: StayDates }) {
  const timezone = property.timezone ?? "Europe/Belgrade";
  const today = propertyToday(timezone);
  const minimum = property.minimum_nights ?? 1;
  const [arrival, setArrival] = useState(initialDates?.check_in ?? shiftDate(today, 1));
  const [departure, setDeparture] = useState(initialDates?.check_out ?? shiftDate(today, 1 + minimum));
  const [guests, setGuests] = useState(initialDates?.guests ?? 1);
  const [month, setMonth] = useState((initialDates?.check_in ?? today).slice(0, 7));
  const [calendar, setCalendar] = useState<StayCalendar | null>(null);
  const [calendarError, setCalendarError] = useState(false);
  const [calendarVersion, setCalendarVersion] = useState(0);
  const [quote, setQuote] = useState<StayQuote | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [needsLogin, setNeedsLogin] = useState(false);
  const [reservation, setReservation] = useState<Stay | null>(null);
  const requestId = useRef("");
  const start = `${month}-01`;
  const endDate = new Date(`${start}T12:00:00Z`);
  endDate.setUTCMonth(endDate.getUTCMonth() + 1);
  const end = endDate.toISOString().slice(0, 10);

  useEffect(() => {
    const controller = new AbortController();
    api.stayCalendar(property.id, start, end, controller.signal).then(value => {
      if (!controller.signal.aborted) { setCalendar(value); setCalendarError(false); }
    }).catch(() => { if (!controller.signal.aborted) setCalendarError(true); });
    return () => controller.abort();
  }, [property.id, start, end, calendarVersion]);

  function invalidate() { setQuote(null); setError(""); setNeedsLogin(false); }
  function reloadCalendar() { setCalendar(null); setCalendarError(false); setCalendarVersion(value => value + 1); }
  function moveMonth(delta: number) {
    const date = new Date(`${start}T12:00:00Z`);
    date.setUTCMonth(date.getUTCMonth() + delta);
    setCalendar(null); setCalendarError(false); setMonth(date.toISOString().slice(0, 7));
  }
  async function checkPrice() {
    setBusy(true); invalidate();
    try {
      const next = await api.stayQuote(property.id, { check_in: arrival, check_out: departure, guests });
      requestId.current = crypto.randomUUID(); setQuote(next);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 409 ? "Izabrani datumi su zauzeti. Izaberi drugi boravak." : "Provera nije uspela. Proveri datume, minimalan boravak i broj gostiju, pa pokušaj ponovo.");
      reloadCalendar();
    } finally { setBusy(false); }
  }
  async function reserve() {
    if (!quote || busy) return;
    setBusy(true); setError("");
    try {
      setReservation(await api.createStay(property.id, { check_in: arrival, check_out: departure, guests, request_id: requestId.current, expected_total_cents: quote.total_cents, expected_currency: quote.currency, expected_check_in_time: quote.check_in_time ?? null, expected_check_out_time: quote.check_out_time ?? null, expected_timezone: quote.timezone }));
      reloadCalendar();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { setNeedsLogin(true); setError("Prijavi se na svoj nalog da potvrdiš rezervaciju."); }
      else if (err instanceof ApiError && [400, 404, 409, 422].includes(err.status)) { setQuote(null); setError("Dostupnost ili uslovi su se promenili. Ponovo proveri cenu i datume."); reloadCalendar(); }
      else setError("Potvrda nije stigla. Pokušaj ponovo sa istim datumima; ponovljeni zahtev neće napraviti duplu rezervaciju.");
    } finally { setBusy(false); }
  }

  if (reservation) return <section className="stay-success" role="status"><h4>{reservation.status === "cancelled" ? "Rezervacija je otkazana" : "Rezervacija je potvrđena"} · #{reservation.id}</h4><p>{displayDate(reservation.check_in)} — {displayDate(reservation.check_out)}</p><p>{stayMoney(reservation.total_cents, reservation.currency)} · Plaćanje kod domaćina</p><StayTimes {...reservation} /><a href="/stays">Pregledaj svoje boravke ↗</a></section>;

  const days = Array.from({ length: Math.round((Date.parse(end) - Date.parse(start)) / 86400000) }, (_, i) => shiftDate(start, i));
  const weekday = (new Date(`${start}T12:00:00Z`).getUTCDay() + 6) % 7;
  return <section className="stay-booking" aria-label={`Rezervacija: ${property.title}`}>
    <h4>Rezerviši ceo stan</h4>
    <p>Do {property.max_guests ?? 2} gostiju · Najmanje {minimum} noćenja</p>
    <div className="stay-month"><button type="button" aria-label="Prethodni mesec" disabled={month <= today.slice(0, 7)} onClick={() => moveMonth(-1)}>‹</button><strong>{new Intl.DateTimeFormat("sr-Latn", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${start}T12:00:00Z`))}</strong><button type="button" aria-label="Sledeći mesec" disabled={month >= shiftDate(today, 365).slice(0, 7)} onClick={() => moveMonth(1)}>›</button></div>
    {calendarError ? <p role="alert">Kalendar nije dostupan. <button type="button" onClick={reloadCalendar}>Pokušaj ponovo</button></p> : !calendar ? <p role="status">Učitavanje kalendara…</p> : <><div className="stay-calendar" aria-label="Kalendar zauzetih noći">{["P", "U", "S", "Č", "P", "S", "N"].map((day, i) => <small key={i} aria-hidden="true">{day}</small>)}{Array.from({ length: weekday }, (_, i) => <span key={`blank-${i}`} />)}{days.map(day => {
      const occupied = calendar.occupied.some(range => range.check_in <= day && day < range.check_out);
      const past = day <= today;
      return <span key={day} className={occupied ? "occupied" : past ? "past" : ""} aria-label={`${displayDate(day)}: ${occupied ? "zauzeto" : past ? "dolazak nije dostupan" : "slobodna noć"}`}>{Number(day.slice(-2))}</span>;
    })}</div><p className="stay-legend">Precrtano = zauzeta noć. Datum odlaska ne zauzima narednu noć.</p></>}
    <form onSubmit={event => { event.preventDefault(); checkPrice(); }}>
      <fieldset disabled={busy}>
        <label>Dolazak<input type="date" required value={arrival} min={shiftDate(today, 1)} max={shiftDate(today, 364)} onChange={event => { setArrival(event.target.value); invalidate(); }} /></label>
        <label>Odlazak<input type="date" required value={departure} min={arrival ? shiftDate(arrival, minimum) : shiftDate(today, 2)} max={shiftDate(today, 365)} onChange={event => { setDeparture(event.target.value); invalidate(); }} /></label>
        <label>Broj gostiju<input type="number" required min={1} max={property.max_guests ?? 2} value={guests} onChange={event => { setGuests(Number(event.target.value)); invalidate(); }} /></label>
        <button className="ph-outline" type="submit">{busy ? "Provera…" : "Proveri dostupnost i cenu"}</button>
      </fieldset>
    </form>
    <p className="stay-legend">Datumi važe u zoni {timezone}. Dolazak je moguć od sutra, a boravak traje do 90 noći.</p>
    {error && <p role="alert">{error} {needsLogin && <a href="/account">Prijavi se ↗</a>}</p>}
    {quote && <div className="stay-quote"><StayTimes {...quote} /><p>{quote.nights} noćenja × {stayMoney(quote.nightly_rate_cents, quote.currency)}</p><strong>Ukupno {stayMoney(quote.total_cents, quote.currency)}</strong><p>Plaćanje kod domaćina. Sada ništa ne naplaćujemo. Besplatno otkazivanje pre dana dolaska.</p><button className="ph-primary" type="button" disabled={busy} onClick={reserve}>{busy ? "Potvrđivanje…" : "Potvrdi rezervaciju"}</button></div>}
  </section>;
}
