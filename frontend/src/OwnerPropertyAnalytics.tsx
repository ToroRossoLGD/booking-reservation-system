import { useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { PropertyAnalytics } from "./property-analytics-types";
import { stayMoney } from "./stay-types";
import "./property-home.css";
import "./stays.css";
import "./property-analytics.css";

const months = ["Januar", "Februar", "Mart", "April", "Maj", "Jun", "Jul", "Avgust", "Septembar", "Oktobar", "Novembar", "Decembar"];
const metrics = { views: "Pregledi detalja", reservations: "Potvrđene rezervacije", nights: "Noćenja", cancelled: "Otkazane rezervacije" };
function money(values: Record<string, number>) { return Object.entries(values).sort(([a], [b]) => a.localeCompare(b)).map(([currency, cents]) => stayMoney(cents, currency)).join(" · ") || "—"; }

export default function OwnerPropertyAnalytics() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [yearInput, setYearInput] = useState(String(year));
  const [propertyId, setPropertyId] = useState<number | undefined>();
  const [data, setData] = useState<PropertyAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const [metric, setMetric] = useState<keyof typeof metrics>("reservations");
  useEffect(() => {
    const controller = new AbortController();
    api.propertyAnalytics(year, propertyId, controller.signal).then(result => { if (!controller.signal.aborted) { setData(result); setLoading(false); } }).catch(err => { if (!controller.signal.aborted) { setLoading(false); setError(err instanceof ApiError && [401, 403].includes(err.status) ? "Prijavi se kao vlasnik da vidiš analitiku svojih oglasa." : "Analitika nije učitana. Pokušaj ponovo."); } });
    return () => controller.abort();
  }, [year, propertyId, version]);
  function refresh() { setLoading(true); setError(""); setVersion(value => value + 1); }
  const totals = { views: 0, reservations: 0, nights: 0, cancelled: 0 };
  const values: Record<string, number> = {};
  for (const month of data?.months ?? []) {
    for (const key of Object.keys(totals) as (keyof typeof totals)[]) totals[key] += month[key];
    for (const [currency, cents] of Object.entries(month.booked_value_cents)) values[currency] = (values[currency] ?? 0) + cents;
  }
  const maximum = Math.max(1, ...(data?.months.map(month => month[metric]) ?? []));
  return <div className="stay-page analytics-page"><header><a className="ph-brand" href="/">bookica.</a><a href="/owner">Vlasnički panel ↗</a></header><main>
    <p className="ph-eyebrow">TVOJI OGLASI</p><h1>Analitika nekretnina</h1><p>Pregledi oglasa i mesečni pregled rezervacija stana na dan.</p>
    <nav className="stay-page-nav"><a href="/owner/stays">Rezervacije stanova</a><a href="/owner/rentals">Upiti za najam</a></nav>
    <form className="analytics-filters" onSubmit={event => { event.preventDefault(); setYear(Number(yearInput)); refresh(); }}>
      <label>Godina<input type="number" min={2000} max={2100} required value={yearInput} onChange={event => setYearInput(event.target.value)} /></label>
      <label>Oglas<select value={propertyId ?? ""} onChange={event => { setPropertyId(event.target.value ? Number(event.target.value) : undefined); refresh(); }}><option value="">Svi moji oglasi</option>{data?.properties.map(property => <option key={property.id} value={property.id}>{property.title} · #{property.id}</option>)}</select></label>
      <button className="ph-primary" type="submit">Prikaži / osveži</button>
    </form>
    {error && <p role="alert">{error} <button className="ph-outline" onClick={refresh}>Pokušaj ponovo</button> <a href="/account">Moj nalog</a></p>}
    {loading ? <p role="status">Učitavanje analitike…</p> : !error && data && <>
      <h2>Pregled za {data.year}.</h2>
      {!data.properties.length && <p>Još nemaš oglase. <a href="/owner">Kreiraj prvi oglas</a>.</p>}
      <div className="analytics-totals">{(Object.keys(metrics) as (keyof typeof metrics)[]).map(key => <div key={key}><span>{metrics[key]}</span><strong>{totals[key]}</strong></div>)}</div>
      <p><strong>Vrednost potvrđenih rezervacija: {money(values)}</strong></p>
      <p className="analytics-note">Vrednost je raspoređena po noćenjima i valutama. Ovo nije evidencija naplaćenog novca. Uključene su i buduće potvrđene rezervacije.</p>
      <label className="analytics-metric">Prikaži grafikon<select value={metric} onChange={event => setMetric(event.target.value as keyof typeof metrics)}>{Object.entries(metrics).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <figure className="analytics-chart"><figcaption>{metrics[metric]} po mesecima</figcaption>{data.months.map(month => <div className="analytics-bar" key={month.month}><span>{months[month.month - 1]}</span><div aria-hidden="true"><i style={{ width: `${month[metric] / maximum * 100}%` }} /></div><strong>{month[metric]}</strong></div>)}</figure>
      <div className="analytics-table" tabIndex={0} role="region" aria-label="Mesečna analitika"><table><caption>Mesečni podaci za {data.year}.</caption><thead><tr><th scope="col">Mesec</th><th scope="col">Pregledi</th><th scope="col">Potvrđene</th><th scope="col">Otkazane</th><th scope="col">Noćenja</th><th scope="col">Vrednost rezervacija</th></tr></thead><tbody>{data.months.map(month => <tr key={month.month}><th scope="row">{months[month.month - 1]}</th><td>{month.views}</td><td>{month.reservations}</td><td>{month.cancelled}</td><td>{month.nights}</td><td>{money(month.booked_value_cents)}</td></tr>)}</tbody></table></div>
    </>}
    <details className="analytics-help"><summary>Kako računamo podatke?</summary><p>Rezervacije se broje u mesecu dolaska. Noćenja su raspoređena po mesecima boravka, bez dana odlaska. Otkazane rezervacije ne ulaze u noćenja i vrednost. Koristimo sačuvane datume i dogovoreni iznos rezervacije.</p><p>Pregled beležimo pri otvaranju detalja oglasa, najviše jednom dnevno po oglasu i sesiji pregledača (UTC). Otvaranje iz kartice i otvaranje posebne stranice se ne dupliraju u istoj sesiji. Prijavljenom vlasniku ne brojimo preglede sopstvenih oglasa.</p><p>Pregledi počinju da se prikupljaju od uvođenja analitike; raniji pregledi nisu dostupni. Nula znači da nema zabeleženih pregleda. Ovo je približan pokazatelj interesovanja, ne broj jedinstvenih ljudi. Blokiranje praćenja može umanjiti broj.</p></details>
  </main></div>;
}
