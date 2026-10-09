import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "./api";

export default function EmailVerification({ token }: { token: string }) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [account, setAccount] = useState<"loading" | "guest" | "unverified" | "verified" | "error">("loading");
  useEffect(() => {
    if (token) return;
    let active = true;
    api.me().then(user => { if (active) setAccount(user.email_verified ? "verified" : "unverified"); })
      .catch(error => { if (active) setAccount(error instanceof ApiError && error.status === 401 ? "guest" : "error"); });
    return () => { active = false; };
  }, [token]);

  async function submit(confirm: boolean) {
    setBusy(true); setError(""); setSent(false);
    try {
      if (confirm) { await api.confirmEmailVerification(token); setDone(true); }
      else { await api.requestEmailVerification(); setSent(true); }
    } catch (error) {
      if (error instanceof ApiError && error.status === 429) setError(error.message);
      else if (error instanceof ApiError && [400, 409, 410, 422].includes(error.status)) setError("Link nije važeći, istekao je ili je već iskorišćen. Zatražite novi link.");
      else if (error instanceof ApiError && error.status === 503) setError("Slanje trenutno nije dostupno. Pokušajte kasnije. U demo režimu potvrda nije potrebna.");
      else if (error instanceof ApiError && error.status === 403) setError("Potvrda nije dostupna u demo režimu i nije potrebna za demo rezervacije.");
      else if (error instanceof ApiError && error.status === 401) setError("Prijavite se da zatražite novi link.");
      else setError("Zahtev nije uspeo. Proverite vezu i pokušajte ponovo.");
    } finally { setBusy(false); }
  }

  return <main id="main-content" tabIndex={-1} className="recovery-page">
    <Link to="/">Bookica</Link>
    <h1>Potvrda email adrese</h1>
    {done || account === "verified" ? <p role="status">Email adresa je potvrđena. Možete nastaviti sa rezervacijama i upitima.</p> : <>
      <p>Potvrdite adresu za nove rezervacije stana na dan i upite za izdavanje ili prodaju.</p>
      {token ? <button disabled={busy} onClick={() => void submit(true)}>{busy ? "Potvrđivanje…" : "Potvrdi email"}</button> : account === "loading" ? <p role="status">Učitavanje…</p> : account === "unverified" ? <button disabled={busy || sent} onClick={() => void submit(false)}>{busy ? "Slanje…" : "Pošalji novi link"}</button> : account === "guest" ? <p>Prijavite se da zatražite novi link za svoj nalog.</p> : <p role="alert">Nalog nije učitan. Osvežite stranicu i pokušajte ponovo.</p>}
      {sent && <p role="status">Ako je potvrda potrebna, link će biti poslat na adresu vašeg naloga. Proverite i spam folder. Novi zahtev je moguć posle jednog minuta; osvežite stranicu pre ponovnog slanja.</p>}
      {token && <a href="/verify-email">Zatraži novi link</a>}
    </>}
    {error && <p role="alert">{error}</p>}
    <a href="/account">Nazad na nalog</a>
  </main>;
}
