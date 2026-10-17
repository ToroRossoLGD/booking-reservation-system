import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "./api";

export default function EmailVerification({ token }: { token: string }) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [sent, setSent] = useState(false);
  const [retryAt, setRetryAt] = useState(0);
  const [remaining, setRemaining] = useState(0);
  useEffect(() => {
    if (!retryAt) return;
    const update = () => {
      const seconds = Math.max(0, Math.ceil((retryAt - Date.now()) / 1000));
      setRemaining(seconds);
      if (seconds === 0) window.clearInterval(timer);
    };
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [retryAt]);
  function waitBeforeResend(seconds: number) {
    setRemaining(seconds);
    setRetryAt(Date.now() + seconds * 1000);
  }
  const [error, setError] = useState("");
  const [statusVersion, setStatusVersion] = useState(0);
  const [account, setAccount] = useState<"loading" | "guest" | "unverified" | "verified" | "error">("loading");
  useEffect(() => {
    if (token) return;
    let active = true;
    api.me().then(user => { if (active) setAccount(user.email_verified ? "verified" : "unverified"); })
      .catch(error => { if (active) setAccount(error instanceof ApiError && error.status === 401 ? "guest" : "error"); });
    return () => { active = false; };
  }, [token, statusVersion]);
  function refreshStatus() {
    if (busy || account === "loading") return;
    setAccount("loading"); setError(""); setSent(false);
    setStatusVersion(value => value + 1);
  }

  async function submit(confirm: boolean) {
    if (busy || (!confirm && remaining > 0)) return;
    setBusy(true); setError(""); setSent(false);
    try {
      if (confirm) { await api.confirmEmailVerification(token); setDone(true); }
      else { await api.requestEmailVerification(); setSent(true); waitBeforeResend(60); }
    } catch (error) {
      if (error instanceof ApiError && error.status === 429) {
        setError(error.message);
        if (!confirm) waitBeforeResend(error.retryAfter ?? 60);
      }
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
      {token ? <button disabled={busy} onClick={() => void submit(true)}>{busy ? "Potvrđivanje…" : "Potvrdi email"}</button> : account === "loading" ? <p role="status">Učitavanje…</p> : account === "unverified" ? <button disabled={busy || remaining > 0} onClick={() => void submit(false)}>{busy ? "Slanje…" : "Pošalji novi link"}</button> : account === "guest" ? <p>Prijavite se da zatražite novi link za svoj nalog.</p> : <p role="alert">Nalog nije učitan. Proverite vezu i pokušajte ponovo.</p>}
      {sent && <p role="status">Ako je potvrda potrebna, link će biti poslat na adresu vašeg naloga. Proverite i spam folder.</p>}
      {!token && account === "unverified" && retryAt > 0 && <>
        {remaining > 0 && <p>Ponovno slanje za {remaining} s.</p>}
        {remaining === 0 ? <p role="status">Možete ponovo zatražiti link.</p> : <p>Sačekajte pre ponovnog slanja. Stranicu nije potrebno osvežavati.</p>}
      </>}
      {token && <a href="/verify-email">Zatraži novi link</a>}
    </>}
    {!token && <button aria-disabled={busy || account === "loading"} onClick={refreshStatus}>Proveri status potvrde</button>}
    {error && <p role="alert">{error}</p>}
    <a href="/account">Nazad na nalog</a>
  </main>;
}
