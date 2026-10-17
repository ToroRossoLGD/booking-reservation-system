import { useEffect, useId, useRef, useState } from "react";
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
  const description = useRef<HTMLTextAreaElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const confirmation = useRef<HTMLParagraphElement>(null);
  useEffect(() => { if (sent && open) confirmation.current?.focus(); }, [sent, open]);
  const fieldId = useId();
  const [invalid, setInvalid] = useState(false);
  function changed() { requestId.current = ""; setError(""); setInvalid(false); }
  function close() { setOpen(false); trigger.current?.focus(); }
  async function submit() {
    if (busy) return;
    if (details.length > 2000) {
      setInvalid(true); setError("Skrati opis na najviše 2000 znakova."); description.current?.focus(); return;
    }
    if (details.trim().length < 10) {
      setInvalid(true); setError("Opiši problem sa najmanje 10 znakova, bez razmaka na početku i kraju.");
      description.current?.focus(); return;
    }
    setBusy(true); setError("");
    if (!requestId.current) requestId.current = crypto.randomUUID();
    try { await api.reportProperty(propertyId, { category, details: details.trim(), request_id: requestId.current }); setSent(true); }
    catch (err) {
      setError(err instanceof ApiError && err.status === 429 && err.retryAfter !== undefined ? err.message : err instanceof ApiError && err.status === 401 ? "Prijavi se da pošalješ prijavu." : err instanceof ApiError && err.status === 409 ? "Za ovaj oglas već postoji tvoja prijava ili je zahtev promenjen. Proveri svoje prijave." : err instanceof ApiError && [400, 404, 429].includes(err.status) ? "Prijava nije moguća: oglas nije dostupan, pripada tebi ili je dostignut limit od 20 otvorenih prijava." : "Potvrda nije stigla. Pokušaj ponovo; isti zahtev neće biti dupliran.");
    } finally { setBusy(false); }
  }
  return <section className="property-report" aria-label="Prijava oglasa">
    <button ref={trigger} className="ph-outline" disabled={busy} aria-expanded={open} aria-controls={`${fieldId}-panel`} onClick={() => setOpen(value => !value)}>Prijavi oglas</button>
    <div id={`${fieldId}-panel`} hidden={!open}>
    {open && (sent ? <p ref={confirmation} tabIndex={-1} role="status">Prijava je poslata administratoru. <a href="/moderation">Moje prijave</a></p> : <form noValidate onSubmit={event => { event.preventDefault(); void submit(); }}>
      <p>Prijavu pregleda administrator. Vlasnik ne dobija tvoje podatke ni tekst prijave. Ne unosi osetljive lične podatke.</p>
      <fieldset disabled={busy}><label>Razlog prijave<select value={category} onChange={event => { setCategory(event.target.value as typeof category); changed(); }}>{Object.entries(reportCategories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Opis problema<textarea ref={description} required minLength={10} maxLength={2000} aria-invalid={invalid} aria-describedby={`${fieldId}-hint${invalid ? ` ${fieldId}-error` : ""}`} value={details} onChange={event => { setDetails(event.target.value); changed(); }} /></label>
        <p id={`${fieldId}-hint`}>Najmanje 10 znakova bez početnih i završnih razmaka; najviše 2000 znakova. Uneto: {details.length}/2000.</p>
        <button className="ph-primary" type="submit">Pošalji prijavu</button>
        <button className="ph-outline" type="button" onClick={close}>Zatvori obrazac</button>
      </fieldset>{error && <p id={`${fieldId}-error`} role="alert">{error} {!invalid && <><a href="/account">Moj nalog</a> · <a href="/moderation">Moje prijave</a></>}</p>}
    </form>)}
    </div>
  </section>;
}
