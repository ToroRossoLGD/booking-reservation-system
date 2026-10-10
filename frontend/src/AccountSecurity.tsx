import { useEffect, useState } from "react";
import { api, ApiError } from "./api";

export default function AccountSecurity() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api.me().then(user => { if (active) setEmail(user.email); })
      .catch(error => { if (active) setError(error instanceof ApiError && error.status === 401 ? "Prijavi se da upravljaš bezbednošću naloga." : "Nalog nije učitan. Osveži stranicu i pokušaj ponovo."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function revoke() {
    setBusy(true); setError("");
    try {
      await api.logoutAllSessions();
      localStorage.removeItem("bookica_token");
      setConfirm(false); setDone(true); setEmail("");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        localStorage.removeItem("bookica_token");
        setEmail(""); setConfirm(false);
        setError("Ova sesija više ne važi. Prijavi se ponovo; odjava svih uređaja nije potvrđena.");
      } else setError("Odjava svih uređaja nije potvrđena. Proveri vezu i pokušaj ponovo.");
    } finally { setBusy(false); }
  }

  return <main id="main-content" tabIndex={-1} className="recovery-page">
    <a href="/">Bookica</a>
    <h1>Bezbednost naloga</h1>
    {loading ? <p role="status">Učitavanje…</p> : done ? <p role="status">Sve sesije i API ključevi su poništeni, uključujući ovu sesiju. Prijavi se ponovo.</p> : email && <>
      <p>{email}</p>
      <h2>Odjava sa svih uređaja</h2>
      <p>Svi uređaji, uključujući ovaj, moraće ponovo da se prijave. Svi postojeći API ključevi prestaju da važe; integracijama će biti potrebni novi ključevi. Lozinka i rezervacije ostaju sačuvane.</p>
      {confirm ? <fieldset disabled={busy}>
        <legend>Potvrdi odjavu svih uređaja i poništavanje API ključeva</legend>
        <button onClick={() => void revoke()}>{busy ? "Odjavljivanje…" : "Potvrdi odjavu svuda"}</button>
        <button onClick={() => { setConfirm(false); setError(""); }}>Odustani</button>
      </fieldset> : <button onClick={() => setConfirm(true)}>Odjavi sve uređaje</button>}
    </>}
    {error && <p role="alert">{error}</p>}
    <a href="/account">{done || !email ? "Prijavi se" : "Nazad na nalog"}</a>
  </main>;
}
