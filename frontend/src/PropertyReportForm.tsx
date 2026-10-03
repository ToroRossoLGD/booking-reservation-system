import { useRef, useState } from "react";
import { api, ApiError } from "./api";
import { reportCategories } from "./moderation-types";
import "./moderation.css";

export default function PropertyReportForm({ propertyId }: { propertyId: number }) {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<keyof typeof reportCategories>("misleading");
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const requestId = useRef("");
  function changed() { requestId.current = ""; setError(""); }
  async function submit() {
    if (busy) return;
    setBusy(true); setError("");
    if (!requestId.current) requestId.current = crypto.randomUUID();
    try { await api.reportProperty(propertyId, { category, details: details.trim(), request_id: requestId.current }); setSent(true); }
    catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? "Prijavi se da pošalješ prijavu." : err instanceof ApiError && err.status === 409 ? "Za ovaj oglas već postoji tvoja prijava ili je zahtev promenjen. Proveri svoje prijave." : err instanceof ApiError && [400, 404, 429].includes(err.status) ? "Prijava nije moguća: oglas nije dostupan, pripada tebi ili je dostignut limit od 20 otvorenih prijava." : "Potvrda nije stigla. Pokušaj ponovo; isti zahtev neće biti dupliran.");
    } finally { setBusy(false); }
  }
  return <section className="property-report" aria-label="Prijava oglasa">
    <button className="ph-outline" disabled={busy} aria-expanded={open} onClick={() => setOpen(value => !value)}>Prijavi oglas</button>
    {open && (sent ? <p role="status">Prijava je poslata administratoru. <a href="/moderation">Moje prijave</a></p> : <form onSubmit={event => { event.preventDefault(); void submit(); }}>
      <p>Prijavu pregleda administrator. Vlasnik ne dobija tvoje podatke ni tekst prijave. Ne unosi osetljive lične podatke.</p>
      <fieldset disabled={busy}><label>Razlog prijave<select value={category} onChange={event => { setCategory(event.target.value as typeof category); changed(); }}>{Object.entries(reportCategories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Opis problema<textarea required minLength={10} maxLength={2000} value={details} onChange={event => { setDetails(event.target.value); changed(); }} /></label>
        <button className="ph-primary" type="submit" disabled={details.trim().length < 10}>Pošalji prijavu</button>
      </fieldset>{error && <p role="alert">{error} <a href="/account">Moj nalog</a> · <a href="/moderation">Moje prijave</a></p>}
    </form>)}
  </section>;
}
