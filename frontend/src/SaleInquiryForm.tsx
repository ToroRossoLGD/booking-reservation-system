import { useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { PropertyListing } from "./property-types";
import "./stays.css";
import "./rentals.css";

export default function SaleInquiryForm({ property }: { property: PropertyListing }) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [login, setLogin] = useState(false);
  const request = useRef<{ body: string; id: string } | null>(null);
  async function submit() {
    if (busy) return;
    const body = message.trim();
    if (request.current?.body !== body) request.current = { body, id: crypto.randomUUID() };
    setBusy(true); setError(""); setLogin(false);
    try { await api.createSaleInquiry(property.id, { message: body, request_id: request.current.id }); setSent(true); }
    catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      setLogin(status === 401);
      setError(status === 401 ? "Prijavi se da pošalješ upit za kupovinu." : status === 409 ? "Već imaš aktivan upit za ovu nekretninu. Proveri svoje upite." : [400, 404].includes(status) ? "Oglas nije dostupan za upite za kupovinu ili pripada tebi. Osveži oglas." : "Potvrda nije stigla. Pokušaj ponovo; isti upit neće biti dupliran.");
    } finally { setBusy(false); }
  }
  if (sent) return <section className="stay-success" role="status"><h4>Upit za kupovinu je poslat</h4><p>Odgovor vlasnika i predlog razgledanja prati u svojim upitima.</p><a href="/sales">Moji upiti za kupovinu</a></section>;
  return <section className="stay-booking rental-form" aria-label={`Upit za kupovinu: ${property.title}`}><h4>Zainteresovan/a za kupovinu?</h4><p>Pošalji pitanje i dogovori razgledanje. Upit ne rezerviše nekretninu, ne predstavlja kupoprodajni ugovor i ništa se ne naplaćuje.</p>
    <form onSubmit={event => { event.preventDefault(); void submit(); }}><fieldset disabled={busy}><label>Poruka prodavcu<textarea required minLength={10} maxLength={3000} rows={4} value={message} onChange={event => setMessage(event.target.value)} placeholder="Napiši pitanja o nekretnini i kada ti odgovara razgledanje." /></label><button className="ph-primary" type="submit" disabled={message.trim().length < 10}>{busy ? "Slanje…" : "Pošalji upit za kupovinu"}</button></fieldset></form>
    {error && <p role="alert">{error} {login && <a href="/account">Prijavi se</a>}</p>}<a href="/sales">Moji upiti za kupovinu</a>
  </section>;
}
