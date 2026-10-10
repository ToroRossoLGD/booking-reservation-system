import { useEffect, useState } from "react";
import CalendarDownloadButton from "./CalendarDownloadButton";
import { viewingCalendar } from "./calendar-export";
import { api, ApiError } from "./api";
import type { SaleInquiry, SaleInquiryPage, RentalInquiry, RentalInquiryPage, RentalUpdate } from "./rental-types";
import { rentalStatus } from "./rental-types";
import { displayDate, stayMoney } from "./stay-types";
import RentalTermsDisplay from "./RentalTermsDisplay";
import RentalConversation from "./RentalConversation";
import "./stays.css";
import "./rentals.css";

function InquiryCard({ inquiry, owner, reload }: { inquiry: RentalInquiry | SaleInquiry; owner: boolean; reload: () => void }) {
  const sale = "asking_price_cents" in inquiry;
  const [reply, setReply] = useState(inquiry.owner_reply);
  const [viewing, setViewing] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmClose, setConfirmClose] = useState(false);
  const active = !["closed", "withdrawn"].includes(inquiry.status);
  async function update(data: Omit<RentalUpdate, "version">) {
    setBusy(true); setError("");
    try { await (sale ? api.updateSaleInquiry : api.updateRentalInquiry)(inquiry.id, { ...data, version: inquiry.version }); reload(); }
    catch (err) { setError(err instanceof ApiError && err.status === 429 ? err.message : err instanceof ApiError && err.status === 409 ? "Upit je izmenjen. Osveži listu pre sledeće izmene." : "Izmena nije uspela. Proveri da li je termin u budućnosti i pokušaj ponovo."); }
    finally { setBusy(false); }
  }
  return <article className="rental-form">
    <div className="stay-row"><span>{rentalStatus[inquiry.status]}</span><span>Upit #{inquiry.id}</span></div>
    <h2>{inquiry.title}</h2><p><strong>{stayMoney(sale ? inquiry.asking_price_cents : inquiry.monthly_price_cents, inquiry.currency)}{!sale && " / mesec"}</strong><br />Cena iz oglasa u trenutku slanja upita.</p>
    {!sale && <p>Željeno useljenje: {displayDate(inquiry.move_in)} · {inquiry.duration_months} meseci</p>}
    {!sale && <RentalTermsDisplay terms={inquiry} currency={inquiry.currency} snapshot />}
    <h3>{sale ? "Poruka kupca" : "Poruka zakupca"}</h3><p className="rental-message">{inquiry.message}</p>
    {inquiry.owner_reply && <><h3>Odgovor vlasnika</h3><p className="rental-message">{inquiry.owner_reply}</p></>}
    {inquiry.viewing_at && <p><strong>Razgledanje: {new Intl.DateTimeFormat("sr-Latn", { dateStyle: "medium", timeStyle: "short" }).format(new Date(inquiry.viewing_at))}</strong><br />Vremenska zona: {Intl.DateTimeFormat().resolvedOptions().timeZone}</p>}
    {inquiry.status === "viewing_confirmed" && inquiry.viewing_at && <CalendarDownloadButton create={() => viewingCalendar(inquiry, window.location.origin, owner)} />}
    {active && <fieldset disabled={busy}>
      {owner ? <form onSubmit={event => { event.preventDefault(); void update(viewing ? { action: "propose", owner_reply: reply.trim(), viewing_at: new Date(viewing).toISOString() } : { action: "reply", owner_reply: reply.trim() }); }}>
        <label>{sale ? "Odgovor kupcu" : "Odgovor zakupcu"}<textarea required maxLength={3000} rows={3} value={reply} onChange={event => setReply(event.target.value)} /></label>
        <label>Predloži termin razgledanja (opciono)<input type="datetime-local" value={viewing} onChange={event => setViewing(event.target.value)} /></label>
        <p>Unesi termin u svojoj vremenskoj zoni: {Intl.DateTimeFormat().resolvedOptions().timeZone}. Napiši mesto sastanka u odgovoru.</p>
        <button type="submit">{viewing ? "Pošalji predlog termina" : "Pošalji odgovor"}</button>
      </form> : inquiry.status === "viewing_proposed" && <div className="rental-actions"><button onClick={() => void update({ action: "confirm" })}>Prihvati termin</button><button onClick={() => void update({ action: "decline" })}>Termin mi ne odgovara</button></div>}
      <div className="rental-actions">{confirmClose ? <><p>{owner ? "Zatvori ovaj upit?" : "Povuci ovaj upit?"} Dogovor oko razgledanja više neće biti aktivan.</p><button onClick={() => void update({ action: owner ? "close" : "withdraw" })}>Potvrdi</button><button onClick={() => setConfirmClose(false)}>Odustani</button></> : <button onClick={() => setConfirmClose(true)}>{owner ? "Zatvori upit" : "Povuci upit"}</button>}</div>
    </fieldset>}
    {busy && <p role="status">Čuvanje…</p>}{error && <p role="alert">{error}</p>}
    <RentalConversation sale={sale} inquiryId={inquiry.id} owner={owner} active={active} unreadCount={inquiry.unread_count} />
  </article>;
}

export default function RentalInquiriesPage({ owner = false, sale = false }: { owner?: boolean; sale?: boolean }) {
  const [page, setPage] = useState<RentalInquiryPage | SaleInquiryPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    (sale ? api.saleInquiries : api.rentalInquiries)(owner, offset).then(result => { if (active) { setPage(result); setLoading(false); } }).catch(err => { if (active) { setLoading(false); setError(err instanceof ApiError && [401, 403].includes(err.status) ? "Prijavi se nalogom koji ima pristup ovim upitima." : "Upiti nisu učitani. Pokušaj ponovo."); } });
    return () => { active = false; };
  }, [owner, sale, offset, version]);
  function reload(nextOffset = offset) { setLoading(true); setError(""); setOffset(nextOffset); setVersion(value => value + 1); }
  return <div className="stay-page"><header><a href="/" className="ph-brand">bookica.</a><a href={owner ? "/owner" : "/account"}>{owner ? "Vlasnički panel" : "Moj nalog"}</a></header>
    <main id="main-content" tabIndex={-1}><p className="ph-eyebrow">{sale ? "KUPOVINA I PRODAJA" : "DUGOROČNI NAJAM"}</p><h1>{sale ? owner ? "Upiti za prodaju nekretnina" : "Moji upiti za kupovinu" : owner ? "Upiti za tvoje stanove" : "Moji upiti za najam"}</h1><p>Dogovor oko razgledanja na jednom mestu. Upit i potvrđeno razgledanje ne predstavljaju rezervaciju ili {sale ? "kupoprodajni ugovor" : "ugovor o zakupu"}.</p>
      <nav className="stay-page-nav"><a href="/account/notifications">Obaveštenja</a><a href="/">Pronađi stan</a><a href={sale ? "/sales" : "/rentals"}>Moji upiti</a><a href={sale ? "/owner/sales" : "/owner/rentals"}>Za vlasnike</a><a href={sale ? "/rentals" : "/sales"}>{sale ? "Upiti za najam" : "Upiti za kupovinu"}</a><button disabled={loading} onClick={() => reload()}>Osveži upite</button></nav>
      {error && <div role="alert"><p>{error}</p><a href="/account">Otvori nalog / prijavu</a></div>}
      {loading ? <p role="status">Učitavanje upita…</p> : !error && page && <><p>Ukupno: {page.total}</p>{page.items.length === 0 && <p>Još nema upita za prikaz.</p>}<div className="stay-list">{page.items.map(inquiry => <InquiryCard key={`${inquiry.id}-${inquiry.version}`} inquiry={inquiry} owner={owner} reload={reload} />)}</div><nav className="ph-pagination" aria-label="Stranice upita"><button disabled={offset === 0} onClick={() => reload(Math.max(0, offset - 20))}>Prethodna</button><button disabled={!page.has_next} onClick={() => reload(offset + 20)}>Sledeća</button></nav></>}
    </main></div>;
}
