import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { api, ApiError } from "./api";
import type { User } from "./types";
import type { ModerationAction, ModerationCase, ModerationEvent, ModerationPageData, PropertyReport } from "./moderation-types";
import { moderationLabels, reportCategories } from "./moderation-types";
import { stayMoney } from "./stay-types";
import "./property-home.css";
import "./stays.css";
import "./moderation.css";

function tokenSnapshot() { try { return localStorage.getItem("bookica_token") ?? ""; } catch { return ""; } }
function subscribe(callback: () => void) { window.addEventListener("storage", callback); window.addEventListener("focus", callback); return () => { window.removeEventListener("storage", callback); window.removeEventListener("focus", callback); }; }

export default function PropertyModerationPage() {
  const token = useSyncExternalStore(subscribe, tokenSnapshot);
  return <div className="stay-page moderation-page"><header><a className="ph-brand" href="/">bookica.</a><a href="/account">Moj nalog</a></header><main id="main-content" tabIndex={-1}><h1>Prijave i moderacija oglasa</h1><nav><a href="/owner">Moji oglasi</a> · <a href="/account/notifications">Obaveštenja</a></nav>{token ? <Authenticated key={token} token={token} /> : <p><a href="/account">Prijavi se</a> da pregledaš prijave i odluke o svojim oglasima.</p>}</main></div>;
}

function Authenticated({ token }: { token: string }) {
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    api.me().then(result => { if (active && tokenSnapshot() === token) setUser(result); }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [token, retry]);
  return error ? <p role="alert">Nalog nije učitan. <button onClick={() => { setError(false); setRetry(value => value + 1); }}>Pokušaj ponovo</button></p> : user ? <Queue user={user} token={token} /> : <p role="status">Provera naloga…</p>;
}

function Queue({ user, token }: { user: User; token: string }) {
  const admin = user.role === "admin";
  const [tab, setTab] = useState<"reports" | "cases">("reports");
  const [status, setStatus] = useState("pending");
  const [caseState, setCaseState] = useState("");
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [reports, setReports] = useState<ModerationPageData<PropertyReport> | null>(null);
  const [cases, setCases] = useState<ModerationPageData<ModerationCase> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  function refresh(nextOffset = offset) { setLoading(true); setError(""); setOffset(nextOffset); setVersion(value => value + 1); }
  useEffect(() => {
    const controller = new AbortController();
    const task = tab === "reports" ? api.propertyReports(admin, status, offset, controller.signal).then(result => { if (!controller.signal.aborted) setReports(result); }) : api.moderationCases(admin, offset, controller.signal, caseState).then(result => { if (!controller.signal.aborted) setCases(result); });
    task.then(() => { if (!controller.signal.aborted) setLoading(false); }).catch(() => { if (!controller.signal.aborted) { setLoading(false); setError("Pregled nije učitan. Proveri prijavu i pokušaj ponovo."); } });
    return () => controller.abort();
  }, [admin, tab, status, caseState, offset, version]);
  const page = tab === "reports" ? reports : cases;
  return <>
    <div className="moderation-tabs"><button className="ph-outline" aria-pressed={tab === "reports"} onClick={() => { setTab("reports"); refresh(0); }}>{admin ? "Prijave korisnika" : "Moje prijave"}</button>{["owner", "admin"].includes(user.role) && <button className="ph-outline" aria-pressed={tab === "cases"} onClick={() => { setTab("cases"); refresh(0); }}>{admin ? "Odluke i zahtevi vlasnika" : "Odluke o mojim oglasima"}</button>}<button className="ph-outline" disabled={loading} onClick={() => refresh()}>Osveži pregled</button></div>
    {admin && tab === "reports" && <label>Status prijave<select value={status} onChange={event => { setStatus(event.target.value); refresh(0); }}><option value="pending">Čeka pregled</option><option value="dismissed">Odbijene</option><option value="action_taken">Preduzeta mera</option></select></label>}
    {admin && tab === "cases" && <label>Status oglasa<select value={caseState} onChange={event => { setCaseState(event.target.value); refresh(0); }}><option value="">Svi statusi</option>{(["appealed", "suspended", "clear"] as const).map(value => <option key={value} value={value}>{moderationLabels[value]}</option>)}</select></label>}
    {error && <p role="alert">{error}</p>}
    {loading ? <p role="status">Učitavanje pregleda…</p> : !error && <>
      <p>Ukupno: {page?.total ?? 0}</p>{!page?.items.length && <p>Nema stavki za prikaz.</p>}
      {tab === "reports" ? reports?.items.map(report => <article key={report.id} className="moderation-card"><h2>Prijava #{report.id} · {report.listing.title}</h2><p>{moderationLabels[report.status]} · {reportCategories[report.category]}</p><p className="moderation-note">{report.details}</p><details><summary>Oglas u trenutku prijave</summary><p>{report.snapshot.title} ? {report.snapshot.city} ? {stayMoney(report.snapshot.price_cents, report.snapshot.currency)}</p><p className="moderation-note">{report.snapshot.description}</p></details>{admin && <><a href={`/owner/properties/${report.property_id}/preview`}>Privatni pregled oglasa</a>{report.status === "pending" && <Decision key={`${report.id}:${report.listing.version}`} listing={report.listing} reportId={report.id} actions={report.listing.state === "clear" ? ["dismiss", "hide"] : ["dismiss"]} token={token} onDone={() => refresh()} />}</>}</article>) : cases?.items.map(listing => <article key={listing.id} className="moderation-card"><h2>{listing.title} · #{listing.id}</h2><p><strong>{moderationLabels[listing.state]}</strong></p>{listing.note && <p className="moderation-note">Obrazloženje administratora: {listing.note}</p>}{listing.appeal && <p className="moderation-note">Poslednji zahtev vlasnika: {listing.appeal}</p>}
        <p><a href={`/owner/properties/${listing.id}/preview`}>Privatni pregled oglasa</a> · <a href="/owner">Izmeni nacrt</a></p>{listing.state === "clear" && !listing.is_published && <p>Zabrana objavljivanja je ukinuta. Proveri nacrt i objavi ga iz svog panela.</p>}
        {((admin && listing.state !== "clear") || (!admin && listing.state === "suspended")) && <Decision key={`${listing.id}:${listing.version}`} listing={listing} actions={admin ? listing.state === "appealed" ? ["restore", "uphold"] : ["restore"] : ["appeal"]} token={token} onDone={() => refresh()} />}
        <History propertyId={listing.id} />
      </article>)}
      <nav className="ph-pagination" aria-label="Stranice moderacije"><button className="ph-outline" disabled={offset === 0} onClick={() => refresh(Math.max(0, offset - 20))}>Prethodna</button><button className="ph-outline" disabled={!page?.has_next} onClick={() => refresh(offset + 20)}>Sledeća</button></nav>
    </>}
  </>;
}

const actionLabels = { hide: "Suspenduj oglas", dismiss: "Zatvori prijavu bez uklanjanja", appeal: "Zatraži ponovni pregled", restore: "Ukini zabranu objavljivanja", uphold: "Potvrdi suspenziju" };
function Decision({ listing, reportId, actions, onDone, token }: { listing: ModerationCase; reportId?: number; actions: ModerationAction["action"][]; onDone: () => void; token: string }) {
  const [note, setNote] = useState("");
  const [action, setAction] = useState(actions[0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [stale, setStale] = useState(false);
  const requestId = useRef("");
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function submit() {
    if (busy || stale || tokenSnapshot() !== token) return;
    setBusy(true); setError("");
    if (!requestId.current) requestId.current = crypto.randomUUID();
    try {
      await api.moderateProperty(listing.id, { request_id: requestId.current, version: listing.version, action, note: note.trim() }, reportId);
      if (mounted.current && tokenSnapshot() === token) onDone();
    } catch (err) {
      if (mounted.current && tokenSnapshot() === token) {
        const conflict = err instanceof ApiError && err.status === 409;
        setStale(conflict); setError(conflict ? "Odluka je u međuvremenu promenjena. Osveži pregled pre nove odluke." : "Izmena nije potvrđena. Proveri pristup i pokušaj ponovo; isti zahtev neće biti dupliran.");
      }
    } finally { if (mounted.current) setBusy(false); }
  }
  return <form onSubmit={event => { event.preventDefault(); void submit(); }}><fieldset disabled={busy || stale}>
    <label>Radnja<select value={action} onChange={event => { setAction(event.target.value as typeof action); requestId.current = ""; }}>{actions.map(value => <option value={value} key={value}>{actionLabels[value]}</option>)}</select></label>
    <label>Obrazloženje za vlasnika i administraciju<textarea required minLength={10} maxLength={2000} value={note} onChange={event => { setNote(event.target.value); requestId.current = ""; }} /></label>
    <p>{action === "hide" ? "Oglas će biti uklonjen iz javne ponude. Postojeće rezervacije ostaju važeće." : action === "restore" ? "Vlasnik će moći da objavi nacrt; oglas se sada ne objavljuje automatski." : "Tekst ostaje u istoriji moderacije. Ne kopiraj lične podatke podnosioca prijave."}</p>
    <button className="ph-primary" type="submit" disabled={note.trim().length < 10}>{actionLabels[action]}</button>
  </fieldset>{error && <p role="alert">{error}</p>}</form>;
}

function History({ propertyId }: { propertyId: number }) {
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<ModerationPageData<ModerationEvent> | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    api.moderationHistory(propertyId, offset, controller.signal).then(result => { if (!controller.signal.aborted) setData(result); }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [open, propertyId, offset, retry]);
  function reload(next = offset) { setData(null); setError(false); setOffset(next); setRetry(value => value + 1); }
  return <section><button className="ph-outline" aria-expanded={open} onClick={() => { if (!open) reload(0); setOpen(value => !value); }}>Istorija odluka</button>{open && (error ? <p role="alert">Istorija nije učitana. <button onClick={() => reload()}>Pokušaj ponovo</button></p> : !data ? <p role="status">Učitavanje istorije…</p> : <><ol>{data.items.map(event => <li key={event.id}><strong>{moderationLabels[event.action]}</strong> · {new Date(event.created_at).toLocaleString("sr-Latn")}<p className="moderation-note">{event.note}</p></li>)}</ol><button disabled={offset === 0} onClick={() => reload(Math.max(0, offset - 20))}>Novije odluke</button><button disabled={!data.has_next} onClick={() => reload(offset + 20)}>Starije odluke</button></>)}</section>;
}
