import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { api, ApiError } from "./api";
import type { User } from "./types";
import type { OwnerAccessRequest, OwnerAccessPageData } from "./owner-access-types";
import "./owner-access.css";

const labels = { pending: "Na čekanju", approved: "Odobren", rejected: "Odbijen" };
function failure(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Prijavi se ponovo da nastaviš. Ako je zahtev odobren, prethodna sesija je poništena.";
    if (error.status === 403) return "Pristup nije dozvoljen. Proveri ulogu i potvrdu email adrese. Promene nisu dostupne u demo režimu.";
    if (error.status === 409) return "Zahtev ili nalog je u međuvremenu promenjen. Osveži pregled pre sledećeg pokušaja.";
    if (error.status === 429) return error.message;
  }
  return "Zahtev nije potvrđen. Proveri vezu i pokušaj ponovo; sačuvan zahtev neće biti dupliran.";
}
function tokenSnapshot() { return localStorage.getItem("bookica_token") ?? ""; }
function subscribe(callback: () => void) { window.addEventListener("storage", callback); window.addEventListener("focus", callback); return () => { window.removeEventListener("storage", callback); window.removeEventListener("focus", callback); }; }
export default function OwnerAccessPage({ admin = false }: { admin?: boolean }) {
  const token = useSyncExternalStore(subscribe, tokenSnapshot);
  return <AccessContent key={`${admin}:${token}`} admin={admin} token={token} />;
}
function AccessContent({ admin, token }: { admin: boolean; token: string }) {
  const [user, setUser] = useState<User | null>(null);
  const [page, setPage] = useState<OwnerAccessPageData | null>(null);
  const [status, setStatus] = useState("pending");
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [details, setDetails] = useState("");
  const [message, setMessage] = useState("");
  const requestId = useRef("");
  function refresh(nextOffset = offset) { setLoading(true); setError(""); setPage(null); setOffset(nextOffset); setVersion(value => value + 1); }
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    api.me().then(async current => {
      if (!active || tokenSnapshot() !== token) return;
      setUser(current);
      if (admin && current.role !== "admin") { setError("Ovaj pregled je dostupan samo administratoru."); setLoading(false); return; }
      const result = await api.ownerAccessRequests(admin, status, offset, controller.signal);
      if (active && tokenSnapshot() === token) { setPage(result); setLoading(false); }
    }).catch(error => { if (active) { setError(failure(error)); setLoading(false); } });
    return () => { active = false; controller.abort(); };
  }, [admin, status, offset, version, token]);
  async function submit() {
    if (busy) return;
    setBusy(true); setError(""); setMessage("");
    if (!requestId.current) requestId.current = crypto.randomUUID();
    try {
      await api.requestOwnerAccess(details.trim(), requestId.current);
      setDetails(""); requestId.current = ""; setMessage("Zahtev je poslat. Administrator će ga pregledati; vlasnički pristup još nije dodeljen."); refresh(0);
    } catch (error) { setError(failure(error)); }
    finally { setBusy(false); }
  }
  return <div className="owner-access-page"><header><a href="/">bookica.</a><a href="/account">Moj nalog / prijava</a></header><main id="main-content" tabIndex={-1}>
    <h1>{admin ? "Zahtevi za vlasnički pristup" : "Postani vlasnik na Bookici"}</h1>
    <p>{admin ? "Pregledaj zahtev i proveri ovlašćenje podnosioca pre odluke. Obrazloženje će biti vidljivo korisniku." : "Za objavljivanje nekretnina potreban je odobren vlasnički pristup. Slanje zahteva ne dodeljuje ulogu automatski."}</p>
    <nav><a href="/help#vlasnici">Kako funkcioniše objavljivanje?</a>{user?.role === "admin" && <a href={admin ? "/owner-access" : "/admin/owner-access"}>{admin ? "Moj pristup" : "Administratorski pregled"}</a>}<button disabled={busy || loading} onClick={() => refresh()}>Osveži zahteve</button></nav>
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
    {loading ? <p role="status">Učitavanje zahteva…</p> : page && user && <>
      {!admin && offset === 0 && (user.role === "owner" || user.role === "admin" ? <p>Vlasnički pristup je aktivan. <a href="/owner">Otvori vlasnički panel</a></p> : !user.email_verified ? <p><a href="/verify-email">Potvrdi email adresu</a> pre slanja zahteva.</p> : <>
        {page.items.some(item => item.status === "pending") ? <p>Zahtev čeka odluku administratora.</p> : <form onSubmit={event => { event.preventDefault(); void submit(); }}>
          <h2>Zatraži pristup</h2><p>Opiši kakve nekretnine planiraš da oglašavaš i po kom osnovu njima upravljaš. Ne šalji lične dokumente, brojeve računa ili druge osetljive podatke. Tekst vidi administracija.</p>
          <label>Opis planiranih oglasa<textarea required minLength={20} maxLength={2000} disabled={busy} value={details} onChange={event => { setDetails(event.target.value); requestId.current = ""; }} /></label>
          <p>20–2000 znakova. Posle odbijanja, novi zahtev je moguć najranije 24 sata od prethodnog slanja.</p><button disabled={busy || details.trim().length < 20}>{busy ? "Slanje…" : "Pošalji zahtev"}</button>
        </form>}
      </>)}
      {admin && <label>Status zahteva<select disabled={busy} value={status} onChange={event => { setStatus(event.target.value); refresh(0); }}>{Object.entries(labels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>}
      <h2>{admin ? "Pregled zahteva" : "Istorija tvojih zahteva"}</h2>
      {!page.items.length && <p>Nema zahteva za prikaz.</p>}
      {page.items.map(item => <RequestCard key={item.id} item={item} admin={admin} busy={busy} onDecision={async (action, note) => {
        setBusy(true); setError(""); setMessage("");
        try { await api.decideOwnerAccess(item.id, action, note); setMessage("Odluka je sačuvana i korisnik ima obaveštenje u aplikaciji."); refresh(0); }
        catch (error) { setError(failure(error)); }
        finally { setBusy(false); }
      }} />)}
      <nav aria-label="Stranice zahteva"><button disabled={busy || offset === 0} onClick={() => refresh(Math.max(0, offset - 20))}>Prethodna</button><span>Stranica {offset / 20 + 1}</span><button disabled={busy || !page.has_next} onClick={() => refresh(offset + 20)}>Sledeća</button></nav>
    </>}
  </main></div>;
}
function RequestCard({ item, admin, busy, onDecision }: { item: OwnerAccessRequest; admin: boolean; busy: boolean; onDecision: (action: "approved" | "rejected", note: string) => Promise<void> }) {
  const [note, setNote] = useState("");
  const [action, setAction] = useState<"approved" | "rejected" | null>(null);
  return <article><h3>Zahtev #{item.id} — {labels[item.status]}</h3>{admin && <p>Korisnik #{item.user_id} · {item.email}</p>}<p>{new Date(item.created_at).toLocaleString("sr-Latn-RS")}</p><p className="owner-access-text">{item.details}</p>{item.decision_note && <><h4>Obrazloženje odluke</h4><p className="owner-access-text">{item.decision_note}</p><p>{item.decided_at && new Date(item.decided_at).toLocaleString("sr-Latn-RS")}</p></>}
    {admin && item.status === "pending" && <fieldset disabled={busy}><legend>Administratorska odluka</legend><label>Obrazloženje za korisnika<textarea minLength={10} maxLength={2000} value={note} onChange={event => { setNote(event.target.value); setAction(null); }} /></label>{action ? <div><p>{action === "approved" ? "Odobrenje dodeljuje vlasničku ulogu i poništava sve postojeće sesije i API ključeve ovog korisnika. Moraće ponovo da se prijavi." : "Odbijanje zadržava korisničku ulogu. Korisnik će videti obrazloženje."}</p><button disabled={note.trim().length < 10} onClick={() => void onDecision(action, note.trim())}>Potvrdi odluku</button><button onClick={() => setAction(null)}>Odustani</button></div> : <><button disabled={note.trim().length < 10} onClick={() => setAction("approved")}>Odobri pristup</button><button disabled={note.trim().length < 10} onClick={() => setAction("rejected")}>Odbij zahtev</button></>}</fieldset>}
  </article>;
}
