import { useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { RentalMessage, RentalMessagePage } from "./rental-types";

const eventLabels: Record<RentalMessage["kind"], string> = {
  message: "", legacy_reply: "Raniji odgovor vlasnika",
  propose: "Predložen termin razgledanja", confirm: "Termin prihvaćen",
  decline: "Termin odbijen", close: "Upit zatvoren", withdraw: "Upit povučen",
};
function dateTime(value: string) {
  return new Intl.DateTimeFormat("sr-Latn", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function RentalConversation({ inquiryId, owner, active, unreadCount = 0 }: { inquiryId: number; owner: boolean; active: boolean; unreadCount?: number }) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState<RentalMessagePage | null>(null);
  const [unread, setUnread] = useState(unreadCount);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const request = useRef<{ body: string; id: string } | null>(null);
  const role = owner ? "owner" : "tenant";
  const unreadShown = page?.items.filter(message => message.sender !== role && !message.read_at).map(message => message.id) ?? [];

  async function load(beforeId?: number) {
    setBusy(true); setError("");
    try { const result = await api.rentalMessages(inquiryId, beforeId); setPage(result); setUnread(result.unread_count); }
    catch { setError("Razgovor nije učitan. Pokušaj ponovo."); }
    finally { setBusy(false); }
  }
  async function send() {
    const body = draft.trim();
    if (!body || busy) return;
    setBusy(true); setError(""); setNotice("");
    if (request.current?.body !== body) request.current = { body, id: crypto.randomUUID() };
    try {
      await api.sendRentalMessage(inquiryId, body, request.current.id);
      setDraft(""); request.current = null; setNotice("Poruka je poslata.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError && err.status === 409 ? "Poruka nije poslata. Upit je možda zatvoren; osveži upite da proveriš status." : "Slanje nije uspelo. Poruka je sačuvana u formi; pokušaj ponovo.");
    } finally { setBusy(false); }
  }
  async function markRead() {
    setBusy(true); setError("");
    try {
      const result = await api.readRentalMessages(inquiryId, unreadShown);
      setUnread(result.unread_count);
      setPage(current => current ? { ...current, items: current.items.map(message => unreadShown.includes(message.id) ? { ...message, read_at: new Date().toISOString() } : message) } : current);
    } catch { setError("Poruke nisu označene kao pročitane. Pokušaj ponovo."); }
    finally { setBusy(false); }
  }
  return <section className="rental-conversation" aria-label={`Razgovor za upit ${inquiryId}`}>
    <button type="button" className="rental-conversation-toggle" aria-expanded={open} aria-controls={`conversation-${inquiryId}`} disabled={busy} onClick={() => { setOpen(!open); if (!open) void load(); }}>
      {open ? "Sakrij razgovor" : "Otvori razgovor"}{unread > 0 && <span className="rental-unread">{unread} nepročitanih</span>}
    </button>
    {open && <div id={`conversation-${inquiryId}`}>
      <div className="rental-actions"><button type="button" disabled={busy} onClick={() => void load()}>Najnovije poruke / osveži</button>{page?.has_more && <button type="button" disabled={busy} onClick={() => void load(page.next_before_id ?? undefined)}>Starije poruke</button>}</div>
      <p className="rental-conversation-note">Privatan razgovor zakupca i vlasnika. Vremenska zona: {Intl.DateTimeFormat().resolvedOptions().timeZone}.</p>
      {page && <ol className="rental-conversation-messages" aria-label="Istorija razgovora">{page.items.map(message => <li key={message.id} className={message.sender === role ? "is-mine" : ""}>
        <div className="rental-message-meta"><strong>{message.sender === role ? "Ti" : message.sender === "owner" ? "Vlasnik" : "Zakupac"}</strong>{message.created_at && <time dateTime={message.created_at}>{dateTime(message.created_at)}</time>}</div>
        {eventLabels[message.kind] && <p className="rental-event-label">{eventLabels[message.kind]}</p>}
        {message.body && <p className="rental-message">{message.body}</p>}
        {message.viewing_at && <p>Predloženo razgledanje: {dateTime(message.viewing_at)}</p>}
        {message.kind === "legacy_reply" && <small>Datum ranijeg odgovora nije zabeležen.</small>}
        {message.sender !== role && !message.read_at && <small className="rental-unread-label">Nepročitano</small>}
      </li>)}</ol>}
      {page?.items.length === 0 && <p>Još nema poruka.</p>}
      {unreadShown.length > 0 && <button type="button" disabled={busy} onClick={() => void markRead()}>Označi prikazane poruke kao pročitane</button>}
      {active ? <form onSubmit={event => { event.preventDefault(); void send(); }}><fieldset disabled={busy}>
        <label>Nova poruka<textarea required maxLength={3000} rows={3} value={draft} onChange={event => setDraft(event.target.value)} placeholder="Napiši pitanje ili dogovor oko razgledanja…" /></label>
        <button type="submit" disabled={!draft.trim()}>Pošalji poruku</button>
      </fieldset></form> : <p>Upit je završen. Istorija razgovora ostaje dostupna.</p>}
      {busy && <p role="status">Učitavanje…</p>}{notice && <p role="status">{notice}</p>}{error && <p role="alert">{error}</p>}
    </div>}
  </section>;
}
