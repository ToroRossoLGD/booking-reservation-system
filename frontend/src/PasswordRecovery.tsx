import { useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "./api";

function failure(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return error.message;
    if ([400, 409, 410].includes(error.status)) return "Link nije važeći, istekao je ili je već iskorišćen. Zatražite novi link.";
    if (error.status === 403) return "Oporavak lozinke nije dostupan u demo režimu. Koristite dodeljeni demo nalog.";
    if (error.status === 503) return "Oporavak lozinke trenutno nije dostupan. Pokušajte kasnije.";
    if (error.status === 422) return "Proverite unete podatke i dužinu lozinke.";
  }
  return "Zahtev nije uspeo. Proverite vezu i pokušajte ponovo.";
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setSent(false);
    try {
      await api.requestPasswordReset(email.trim());
      setSent(true);
    } catch (error) { setError(failure(error)); }
    finally { setBusy(false); }
  }
  return <main id="main-content" tabIndex={-1} className="recovery-page">
    <Link to="/">Bookica</Link>
    <h1>Zaboravljena lozinka</h1>
    <p>Unesite email adresu naloga da zatražite link za novu lozinku.</p>
    <form onSubmit={submit} className="auth-form">
      <label htmlFor="recovery-email">Email adresa</label>
      <input id="recovery-email" type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} disabled={busy} />
      <button type="submit" disabled={busy}>{busy ? "Slanje…" : "Pošalji link"}</button>
    </form>
    {sent && <p role="status">Ako postoji nalog za ovu adresu, dobićete link za promenu lozinke. Proverite i spam folder. Ako poruka ne stigne, pokušajte ponovo kasnije.</p>}
    {error && <p role="alert">{error}</p>}
    <Link to="/account">Nazad na prijavu</Link>
  </main>;
}

export function ResetPasswordPage({ token }: { token: string }) {
  const passwordInput = useRef<HTMLInputElement>(null);
  const confirmationInput = useRef<HTMLInputElement>(null);
  const [visible, setVisible] = useState(false);
  const [invalidField, setInvalidField] = useState<"password" | "confirmation" | null>(null);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setInvalidField(null); setVisible(false);
    if (password !== confirmation) { setError("Lozinke se ne poklapaju."); setInvalidField("confirmation"); confirmationInput.current?.focus(); return; }
    if (new TextEncoder().encode(password).length > 72) { setError("Lozinka je preduga. Koristite kraću lozinku."); setInvalidField("password"); passwordInput.current?.focus(); return; }
    setBusy(true);
    try {
      await api.confirmPasswordReset(token, password);
      localStorage.removeItem("bookica_token");
      setPassword(""); setConfirmation(""); setDone(true);
    } catch (error) { setError(failure(error)); }
    finally { setBusy(false); }
  }
  return <main id="main-content" tabIndex={-1} className="recovery-page">
    <Link to="/">Bookica</Link>
    <h1>Nova lozinka</h1>
    {done ? <p role="status">Lozinka je promenjena. Prijavite se novom lozinkom; prethodne sesije i API ključevi više ne važe.</p> : !token ? <p role="alert">Link nedostaje ili nije važeći. Otvorite link iz emaila ili zatražite novi.</p> : <>
      <p id="password-guidance">Unesite novu lozinku od najmanje 8 znakova. Link možete iskoristiti samo jednom.</p>
      <form onSubmit={submit} className="auth-form">
        <label htmlFor="new-password">Nova lozinka</label>
        <input ref={passwordInput} id="new-password" type={visible ? "text" : "password"} autoComplete="new-password" autoCapitalize="none" spellCheck={false} aria-invalid={invalidField === "password"} aria-describedby={invalidField === "password" ? "password-guidance reset-error" : "password-guidance"} minLength={8} maxLength={72} required value={password} onChange={event => { setPassword(event.target.value); setInvalidField(null); setError(""); }} disabled={busy} />
        <label htmlFor="confirm-password">Ponovite lozinku</label>
        <input ref={confirmationInput} id="confirm-password" type={visible ? "text" : "password"} autoComplete="new-password" autoCapitalize="none" spellCheck={false} aria-invalid={invalidField === "confirmation"} aria-describedby={invalidField === "confirmation" ? "reset-error" : undefined} minLength={8} maxLength={72} required value={confirmation} onChange={event => { setConfirmation(event.target.value); setInvalidField(null); setError(""); }} disabled={busy} />
        <button type="button" aria-controls="new-password confirm-password" aria-pressed={visible} disabled={busy} onClick={() => setVisible(value => !value)}>Prikaži lozinke</button>
        <button type="submit" disabled={busy}>{busy ? "Čuvanje…" : "Sačuvaj lozinku"}</button>
      </form>
    </>}
    {error && <p id="reset-error" role="alert">{error}</p>}
    {!done && <Link to="/forgot-password">Zatraži novi link</Link>}
    <Link to="/account">Nazad na prijavu</Link>
  </main>;
}
