import { useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { StayPage } from "./stay-types";
import { displayDate, propertyToday, stayMoney } from "./stay-types";
import "./stays.css";

export default function StaysPage({ owner = false }: { owner?: boolean }) {
  const [page, setPage] = useState<StayPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  useEffect(() => {
    let active = true;
    api.myStays(owner, offset).then(result => { if (active) { setPage(result); setLoading(false); } }).catch(err => { if (active) { setLoading(false); setError(err instanceof ApiError && [401, 403].includes(err.status) ? "Prijavi se nalogom koji ima pristup ovim rezervacijama." : "Rezervacije nisu učitane. Pokušaj ponovo."); } });
    return () => { active = false; };
  }, [owner, offset, version]);
  function reload(nextOffset = offset) { setLoading(true); setError(""); setOffset(nextOffset); setVersion(value => value + 1); }
  async function cancel(id: number) {
    setBusy(true); setError("");
    try { await api.cancelStay(id); setConfirmId(null); reload(); }
    catch { setError("Otkazivanje nije uspelo. Moguće je samo pre dana dolaska. Pokušaj ponovo ili kontaktiraj domaćina."); }
    finally { setBusy(false); }
  }
  return <div className="stay-page"><header><a href="/" className="ph-brand">⌂ bookica.</a><a href={owner ? "/owner" : "/account"}>{owner ? "Vlasnički panel" : "Moj nalog"} ↗</a></header><main><p className="ph-eyebrow">STAN NA DAN</p><h1>{owner ? "Rezervacije tvojih stanova" : "Moji boravci"}</h1><p>{owner ? "Pregled dolazaka i odlazaka za tvoje objekte." : "Potvrđeni boravci, dogovoreni iznosi i otkazivanje na jednom mestu."}</p><nav className="stay-page-nav"><a href="/">Pronađi smeštaj</a><a href="/stays">Moji boravci</a><a href="/owner/stays">Za domaćine</a></nav>
      {error && <div role="alert"><p>{error}</p><a href="/account">Otvori nalog / prijavu ↗</a><button className="ph-outline" onClick={() => reload()}>Pokušaj ponovo</button></div>}
      {loading ? <p role="status">Učitavanje rezervacija…</p> : page && <><p>Ukupno: {page.total}</p>{page.items.length === 0 && <p>Još nema rezervacija za prikaz.</p>}<div className="stay-list">{page.items.map(stay => <article key={stay.id}><div className="stay-row"><span>#{stay.id} · {stay.status === "cancelled" ? "Otkazano" : "Potvrđeno"}</span><strong>{stayMoney(stay.total_cents, stay.currency)}</strong></div><h2>{stay.title}</h2><p>{stay.city} · {displayDate(stay.check_in)} — {displayDate(stay.check_out)}</p><p>{stay.guests} gostiju · Plaćanje kod domaćina</p><a href={`mailto:${encodeURIComponent(owner ? stay.guest_email ?? stay.contact_email : stay.contact_email)}`}>{owner ? "Kontakt gosta" : "Kontakt domaćina"} ↗</a>{!owner && stay.status === "confirmed" && stay.check_in > propertyToday(stay.timezone) && <div className="stay-cancel">{confirmId === stay.id ? <><p>Potvrdi besplatno otkazivanje ovog boravka.</p><button disabled={busy} onClick={() => cancel(stay.id)}>Potvrdi otkazivanje</button><button disabled={busy} onClick={() => setConfirmId(null)}>Odustani</button></> : <button onClick={() => setConfirmId(stay.id)}>Otkaži rezervaciju</button>}</div>}</article>)}</div><nav className="ph-pagination" aria-label="Stranice rezervacija"><button className="ph-outline" disabled={offset === 0 || busy} onClick={() => reload(Math.max(0, offset - 20))}>Prethodna</button><button className="ph-outline" disabled={!page.has_next || busy} onClick={() => reload(offset + 20)}>Sledeća</button></nav></>}
    </main></div>;
}
