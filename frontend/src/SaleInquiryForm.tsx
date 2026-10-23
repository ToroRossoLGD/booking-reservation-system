import { useEffect, useId, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { PropertyListing } from "./property-types";
import "./stays.css";
import "./rentals.css";

export default function SaleInquiryForm({ property }: { property: PropertyListing }) {
  const fieldId = useId();
  const input = useRef<HTMLTextAreaElement>(null);
  const confirmation = useRef<HTMLElement>(null);
  const [invalid, setInvalid] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [login, setLogin] = useState(false);
  const request = useRef<{ body: string; id: string } | null>(null);
  useEffect(() => { if (sent) confirmation.current?.focus(); }, [sent]);
  async function submit() {
    if (busy) return;
    const body = message.trim();
    if (Array.from(body).length < 10 || Array.from(body).length > 3000) {
      setInvalid(true);
      setError("Unesi poruku od 10 do 3000 znakova, bez razmaka na početku i kraju.");
      input.current?.focus(); return;
    }
    setInvalid(false);
    if (request.current?.body !== body) request.current = { body, id: crypto.randomUUID() };
    setBusy(true); setError(""); setLogin(false);
    try { await api.createSaleInquiry(property.id, { message: body, request_id: request.current.id }); setSent(true); }
    catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      setLogin(status === 401);
      setError(err instanceof ApiError && status === 429 ? err.message : status === 401 ? "Prijavi se da pošalješ upit za kupovinu." : status === 409 ? "Već imaš aktivan upit za ovu nekretninu. Proveri svoje upite." : [400, 404].includes(status) ? "Oglas nije dostupan za upite za kupovinu ili pripada tebi. Osveži oglas." : "Potvrda nije stigla. Pokušaj ponovo; isti upit neće biti dupliran.");
    } finally { setBusy(false); }
  }
  if (sent) return <section ref={confirmation} tabIndex={-1} className="stay-success" role="status"><h4>Upit za kupovinu je poslat</h4><p>Odgovor vlasnika i predlog razgledanja prati u svojim upitima.</p><a href="/sales">Moji upiti za kupovinu</a></section>;
  return <section className="stay-booking rental-form" aria-label={`Upit za kupovinu: ${property.title}`}><h4>Zainteresovan/a za kupovinu?</h4><p>Pošalji pitanje i dogovori razgledanje. Upit ne rezerviše nekretninu, ne predstavlja kupoprodajni ugovor i ništa se ne naplaćuje.</p>
    <form noValidate onSubmit={event => { event.preventDefault(); void submit(); }}><fieldset disabled={busy}><label>Poruka prodavcu<textarea ref={input} required aria-invalid={invalid} aria-describedby={`${fieldId}-hint${invalid ? ` ${fieldId}-error` : ""}`} rows={4} value={message} onChange={event => { setMessage(event.target.value); setInvalid(false); setError(""); }} placeholder="Napiši pitanja o nekretnini i kada ti odgovara razgledanje." /></label><p id={`${fieldId}-hint`}>10–3000 znakova bez početnih i završnih razmaka. Uneto: {Array.from(message.trim()).length}/3000.</p><button className="ph-primary" type="submit">{busy ? "Slanje…" : "Pošalji upit za kupovinu"}</button></fieldset></form>
    {error && <p id={`${fieldId}-error`} role="alert">{error} {login && <a href="/account">Prijavi se</a>}</p>}<a href="/sales">Moji upiti za kupovinu</a>
  </section>;
}
