import StayTimes from "./StayTimes";
import { useEffect, useState } from "react";
import CalendarDownloadButton from "./CalendarDownloadButton";
import { stayCalendar } from "./calendar-export";
import { api, ApiError } from "./api";
import type { OwnerStayFilters, StayPage } from "./stay-types";
import { displayDate, propertyToday, stayMoney } from "./stay-types";
import "./stays.css";

function OwnerFilters({ page, filters, onChange, loading, onRefresh }: { page: StayPage | null; filters: OwnerStayFilters; onChange: (filters: OwnerStayFilters) => void; loading: boolean; onRefresh: () => void }) {
  return <section className="owner-stay-tools" aria-label="Pregled i filteri rezervacija">
    <div className="owner-stay-summary">
      <button aria-pressed={filters.day === "arrivals"} onClick={() => onChange({ ...filters, day: filters.day === "arrivals" ? undefined : "arrivals", status: undefined })}><span>Danas dolaze</span>{" "}<strong>{loading ? "…" : page?.arrivals_today ?? "—"}</strong></button>
      <button aria-pressed={filters.day === "departures"} onClick={() => onChange({ ...filters, day: filters.day === "departures" ? undefined : "departures", status: undefined })}><span>Danas odlaze</span>{" "}<strong>{loading ? "…" : page?.departures_today ?? "—"}</strong></button>
    </div>
    <p className="stay-legend">Današnji pregled obuhvata potvrđene rezervacije izabranog stana, prema vremenskoj zoni sačuvanoj na rezervaciji. Osveži pregled da dobiješ najnovije stanje.</p>
    <div className="owner-stay-filters">
      <label>Stan<select value={filters.property_id ?? ""} onChange={event => onChange({ ...filters, property_id: event.target.value ? Number(event.target.value) : undefined })}><option value="">Svi stanovi sa rezervacijama</option>{page?.properties?.map(property => <option key={property.id} value={property.id}>{property.title} · #{property.id}</option>)}</select></label>
      <label>Status<select value={filters.status ?? ""} onChange={event => onChange({ ...filters, status: (event.target.value || undefined) as OwnerStayFilters["status"], day: undefined })}><option value="">Svi statusi</option><option value="confirmed">Potvrđene</option><option value="cancelled">Otkazane</option></select></label>
      <button className="ph-outline" onClick={() => onChange({})}>Poništi filtere</button>
      <button className="ph-outline" disabled={loading} onClick={onRefresh}>Osveži pregled</button>
    </div>
    {filters.day && <p role="status">{filters.day === "arrivals" ? "Današnji dolasci" : "Današnji odlasci"} · Po lokalnom vremenu {filters.day === "arrivals" ? "prijave" : "odjave"}. <button className="ph-outline" onClick={() => onChange({ ...filters, day: undefined })}>Prikaži sve datume</button></p>}
  </section>;
}

export default function StaysPage({ owner = false }: { owner?: boolean }) {
  const [page, setPage] = useState<StayPage | null>(null);
  const [filters, setFilters] = useState<OwnerStayFilters>({});
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    api.myStays(owner, offset, filters, controller.signal).then(result => { if (active) { setPage(result); setLoading(false); } }).catch(err => { if (active) { setLoading(false); setError(err instanceof ApiError && [401, 403].includes(err.status) ? "Prijavi se nalogom koji ima pristup ovim rezervacijama." : "Rezervacije nisu učitane. Pokušaj ponovo."); } });
    return () => { active = false; controller.abort(); };
  }, [owner, offset, version, filters]);
  function reload(nextOffset = offset) { setLoading(true); setError(""); setOffset(nextOffset); setVersion(value => value + 1); }
  function changeFilters(next: OwnerStayFilters) { setLoading(true); setError(""); setFilters(next); setOffset(0); }
  async function cancel(id: number) {
    setBusy(true); setError("");
    try { await api.cancelStay(id); setConfirmId(null); reload(); }
    catch { setError("Otkazivanje nije uspelo. Moguće je samo pre dana dolaska. Pokušaj ponovo ili kontaktiraj domaćina."); }
    finally { setBusy(false); }
  }
  return <div className="stay-page"><header><a href="/" className="ph-brand">⌂ bookica.</a><a href={owner ? "/owner" : "/account"}>{owner ? "Vlasnički panel" : "Moj nalog"} ↗</a></header><main><p className="ph-eyebrow">STAN NA DAN</p><h1>{owner ? "Rezervacije tvojih stanova" : "Moji boravci"}</h1><p>{owner ? "Pregled dolazaka i odlazaka za tvoje objekte." : "Potvrđeni boravci, dogovoreni iznosi i otkazivanje na jednom mestu."}</p><nav className="stay-page-nav"><a href="/">Pronađi smeštaj</a><a href="/stays">Moji boravci</a><a href="/owner/stays">Za domaćine</a></nav>
      {owner && <OwnerFilters page={page} filters={filters} onChange={changeFilters} loading={loading || !!error} onRefresh={() => reload()} />}
      {error && <div role="alert"><p>{error}</p><a href="/account">Otvori nalog / prijavu ↗</a><button className="ph-outline" onClick={() => reload()}>Pokušaj ponovo</button></div>}
      {loading ? <p role="status">Učitavanje rezervacija…</p> : !error && page && <><p>Ukupno: {page.total}</p>{page.items.length === 0 && <p>Još nema rezervacija za prikaz.</p>}<div className="stay-list">{page.items.map(stay => <article key={stay.id}><div className="stay-row"><span className={`stay-status ${stay.status}`}>#{stay.id} · {stay.status === "cancelled" ? "Otkazano" : "Potvrđeno"}</span><strong>{stayMoney(stay.total_cents, stay.currency)}</strong></div><h2>{stay.title}</h2><p>{stay.city}</p><dl className="stay-dates"><div><dt>Dolazak</dt><dd>{displayDate(stay.check_in)}</dd></div><div><dt>Odlazak</dt><dd>{displayDate(stay.check_out)}</dd></div></dl><StayTimes {...stay} />{owner && <a className="stay-block-link" href={`/owner?blocks=${stay.property_id}`}>Upravljaj blokadama</a>}<p>{stay.guests} gostiju · Plaćanje kod domaćina</p><a href={`mailto:${encodeURIComponent(owner ? stay.guest_email ?? stay.contact_email : stay.contact_email)}`}>{owner ? "Kontakt gosta" : "Kontakt domaćina"} ↗</a>{stay.status === "confirmed" && <CalendarDownloadButton create={() => stayCalendar(stay, window.location.origin, owner)} />}{!owner && stay.status === "confirmed" && stay.check_in > propertyToday(stay.timezone) && <div className="stay-cancel">{confirmId === stay.id ? <><p>Potvrdi besplatno otkazivanje ovog boravka.</p><button disabled={busy} onClick={() => cancel(stay.id)}>Potvrdi otkazivanje</button><button disabled={busy} onClick={() => setConfirmId(null)}>Odustani</button></> : <button onClick={() => setConfirmId(stay.id)}>Otkaži rezervaciju</button>}</div>}</article>)}</div><nav className="ph-pagination" aria-label="Stranice rezervacija"><button className="ph-outline" disabled={offset === 0 || busy} onClick={() => reload(Math.max(0, offset - 20))}>Prethodna</button><button className="ph-outline" disabled={!page.has_next || busy} onClick={() => reload(offset + 20)}>Sledeća</button></nav></>}
    </main></div>;
}
