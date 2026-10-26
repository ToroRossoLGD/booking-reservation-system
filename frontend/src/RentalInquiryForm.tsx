import { useEffect, useId, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { PropertyListing } from "./property-types";
import RentalTermsDisplay from "./RentalTermsDisplay";
import { propertyToday } from "./stay-types";
import "./stays.css";
import "./rentals.css";

export default function RentalInquiryForm({ property }: { property: PropertyListing }) {
  const fieldId = useId();
  const input = useRef<HTMLTextAreaElement>(null);
  const confirmation = useRef<HTMLElement>(null);
  const [invalid, setInvalid] = useState(false);
  const [moveIn, setMoveIn] = useState("");
  const [months, setMonths] = useState(Math.max(12, property.minimum_rental_months ?? 1));
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [login, setLogin] = useState(false);
  const request = useRef<{ body: string; id: string } | null>(null);

  const today = propertyToday(property.timezone ?? "Europe/Belgrade");
  const earliest = property.available_from && property.available_from > today ? property.available_from : today;

  useEffect(() => { if (sent) confirmation.current?.focus(); }, [sent]);

  async function submit() {
    if (busy) return;
    const length = Array.from(message.trim()).length;
    if (length < 10 || length > 3000) {
      setInvalid(true); setLogin(false);
      setError("Unesi poruku od 10 do 3000 znakova, bez razmaka na početku i kraju.");
      input.current?.focus(); return;
    }
    setInvalid(false);
    setBusy(true); setError(""); setLogin(false);
    const data = { move_in: moveIn, duration_months: months, message: message.trim() };
    const body = JSON.stringify(data);
    if (request.current?.body !== body) request.current = { body, id: crypto.randomUUID() };
    try {
      await api.createRentalInquiry(property.id, { ...data, request_id: request.current.id });
      setSent(true);
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      setLogin(status === 401);
      setError(err instanceof ApiError && status === 429 ? err.message : status === 401 ? "Prijavi se da pošalješ upit." : status === 409 ? "Već imaš aktivan upit za ovaj stan. Proveri svoje upite." : status === 400 ? "Proveri dostupnost i minimalno trajanje najma. Osveži oglas ako su uslovi promenjeni. Upit za sopstveni oglas nije dozvoljen." : "Upit nije poslat. Pokušaj ponovo; uneti podaci su sačuvani u formi.");
    } finally { setBusy(false); }
  }

  if (sent) return <section ref={confirmation} tabIndex={-1} className="stay-success" role="status"><h4>Upit je poslat vlasniku</h4><p>Odgovor i predlog razgledanja prati u svojim upitima.</p><a href="/rentals">Moji upiti za najam</a></section>;
  return <section className="stay-booking rental-form" aria-label={`Upit za najam: ${property.title}`}>
    <h4>Zainteresovan/a za dugoročni najam?</h4>
    <p>Pošalji upit i dogovori razgledanje. Slanje upita ne rezerviše stan i ništa se ne naplaćuje.</p>
    <RentalTermsDisplay terms={property} currency={property.currency} />
    <form onSubmit={event => { event.preventDefault(); void submit(); }}><fieldset disabled={busy}>
      <label>Željeno useljenje<input type="date" required min={earliest} value={moveIn} onChange={event => setMoveIn(event.target.value)} /></label>
      <label>Trajanje najma (meseci)<input type="number" required min={property.minimum_rental_months ?? 1} max={120} value={months} onChange={event => setMonths(Number(event.target.value))} /></label>
      <label>Poruka vlasniku<textarea ref={input} aria-required="true" aria-invalid={invalid} aria-describedby={`${fieldId}-hint${invalid ? ` ${fieldId}-error` : ""}`} rows={4} value={message} onChange={event => { setMessage(event.target.value); setInvalid(false); setError(""); }} placeholder="Predstavi se i napiši kada ti odgovara razgledanje." /></label>
      <p id={`${fieldId}-hint`}>10–3000 znakova bez početnih i završnih razmaka. Uneto: {Array.from(message.trim()).length}/3000.</p>
      <button type="submit" className="ph-primary">{busy ? "Slanje…" : "Pošalji upit za najam"}</button>
    </fieldset></form>
    {error && <p id={`${fieldId}-error`} role="alert">{error} {login && <a href="/account">Prijavi se</a>}</p>}
    <a href="/rentals">Moji upiti za najam</a>
  </section>;
}
