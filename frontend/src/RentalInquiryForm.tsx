import { useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { PropertyListing } from "./property-types";
import { propertyToday } from "./stay-types";
import "./stays.css";
import "./rentals.css";

export default function RentalInquiryForm({ property }: { property: PropertyListing }) {
  const [moveIn, setMoveIn] = useState("");
  const [months, setMonths] = useState(12);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [login, setLogin] = useState(false);
  const request = useRef<{ body: string; id: string } | null>(null);

  async function submit() {
    if (busy) return;
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
      setError(status === 401 ? "Prijavi se da pošalješ upit." : status === 409 ? "Već imaš aktivan upit za ovaj stan. Proveri svoje upite." : status === 400 ? "Proveri datum useljenja. Upit za sopstveni oglas nije dozvoljen." : "Upit nije poslat. Pokušaj ponovo; uneti podaci su sačuvani u formi.");
    } finally { setBusy(false); }
  }

  if (sent) return <section className="stay-success" role="status"><h4>Upit je poslat vlasniku</h4><p>Odgovor i predlog razgledanja prati u svojim upitima.</p><a href="/rentals">Moji upiti za najam</a></section>;
  return <section className="stay-booking rental-form" aria-label={`Upit za najam: ${property.title}`}>
    <h4>Zainteresovan/a za dugoročni najam?</h4>
    <p>Pošalji upit i dogovori razgledanje. Slanje upita ne rezerviše stan i ništa se ne naplaćuje.</p>
    <form onSubmit={event => { event.preventDefault(); void submit(); }}><fieldset disabled={busy}>
      <label>Željeno useljenje<input type="date" required min={propertyToday(property.timezone ?? "Europe/Belgrade")} value={moveIn} onChange={event => setMoveIn(event.target.value)} /></label>
      <label>Trajanje najma (meseci)<input type="number" required min={1} max={120} value={months} onChange={event => setMonths(Number(event.target.value))} /></label>
      <label>Poruka vlasniku<textarea required minLength={10} maxLength={3000} rows={4} value={message} onChange={event => setMessage(event.target.value)} placeholder="Predstavi se i napiši kada ti odgovara razgledanje." /></label>
      <button type="submit" className="ph-primary">{busy ? "Slanje…" : "Pošalji upit za najam"}</button>
    </fieldset></form>
    {error && <p role="alert">{error} {login && <a href="/account">Prijavi se</a>}</p>}
    <a href="/rentals">Moji upiti za najam</a>
  </section>;
}
