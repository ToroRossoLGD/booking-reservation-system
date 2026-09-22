import { useEffect, useState } from "react";
import { api } from "./api";
import PropertyCard from "./PropertyCard";
import SavePropertyButton from "./SavePropertyButton";
import { offerLabels } from "./property-types";
import type { OfferType, PropertyPage } from "./property-types";
import "./property-home.css";
import "./property-refresh.css";

const emptyPage: PropertyPage = { items: [], total: 0, limit: 12, offset: 0, has_next: false };

export default function PropertyHome() {
  const [offer, setOffer] = useState<OfferType | "">("");
  const [location, setLocation] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<PropertyPage>(emptyPage);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  const [favoriteIds, setFavoriteIds] = useState<Set<number> | null>(null);
  const [favoritesError, setFavoritesError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    api.properties(query, offer, offset, controller.signal).then(async result => {
      if (controller.signal.aborted) return;
      setPage(result); setError(false); setLoading(false); setFavoriteIds(null); setFavoritesError(false);
      if (!localStorage.getItem("bookica_token") || result.items.length === 0) { setFavoriteIds(new Set()); return; }
      try {
        const saved = await api.savedPropertyIds(result.items.map(property => property.id), controller.signal);
        if (!controller.signal.aborted) setFavoriteIds(new Set(saved.property_ids));
      } catch {
        if (!controller.signal.aborted) setFavoritesError(true);
      }
    }).catch(() => {
      if (!controller.signal.aborted) { setError(true); setLoading(false); }
    });
    return () => controller.abort();
  }, [query, offer, offset, retry]);

  function search(city: string, type: OfferType | "" = offer) {
    setLocation(city); setQuery(city.trim()); setOffer(type); setOffset(0);
    setLoading(true); setError(false); setRetry(value => value + 1);
  }

  return <div className="property-home">
    <header className="ph-header">
      <a className="ph-brand" href="/" aria-label="Bookica početna"><span>⌂</span> bookica<span className="ph-brand-dot">.</span></a>
      <nav aria-label="Glavna navigacija"><a href="#ponuda">Pronađi nekretninu</a><a href="/saved">Sačuvani oglasi</a><a href="/stays">Moji boravci</a><a href="/rentals">Moji upiti</a><a href="/account">Moj nalog</a></nav>
      <a className="ph-outline" href="/owner">Objavi oglas ↗</a>
    </header>
    <nav className="ph-mobile-nav" aria-label="Mobilna navigacija"><a href="#ponuda">Ponuda</a><a href="/saved">Sačuvano</a><a href="/stays">Boravci</a><a href="/rentals">Upiti</a><a href="/account">Moj nalog ↗</a></nav>
    <main>
      <section className="ph-hero">
        <div className="ph-hero-copy"><p className="ph-eyebrow"><span className="ph-live-dot" /> TVOJE MESTO. TVOJ RITAM.</p><h1>Negde te čeka<br />tvoj <em>novi pogled.</em></h1><p>Za nekoliko dana, novo poglavlje ili ceo život.<br />Pronađi prostor u kom želiš da budeš.</p><a href="#ponuda" className="ph-text-link">Pronađi svoje mesto <span>↗</span></a><div className="ph-hero-note"><span aria-hidden="true">⌂</span><p>Jedna adresa za tvoje planove.<small>Odmor · Dugoročni najam · Novi dom</small></p></div></div>
        <div className="ph-hero-art" role="img" aria-label="Ilustracija sunčane kuće među zelenim brdima"><div className="ph-sun" /><div className="ph-hill ph-hill-back" /><div className="ph-hill" /><div className="ph-house"><div className="ph-window" /><div className="ph-door" /></div><span className="ph-art-caption">Manje svakodnevice. Više tvog sveta.</span></div>
      </section>
      <section className="ph-search" aria-label="Pretraga nekretnina">
        <div className="ph-tabs">
          <button type="button" aria-pressed={offer === ""} className={!offer ? "is-active" : ""} onClick={() => search(query, "")}>Sve nekretnine</button>
          {(Object.keys(offerLabels) as OfferType[]).map(type => <button key={type} type="button" aria-pressed={offer === type} className={offer === type ? "is-active" : ""} onClick={() => search(query, type)}>{offerLabels[type]}</button>)}
        </div>
        <form onSubmit={e => { e.preventDefault(); search(location); document.getElementById("ponuda")?.scrollIntoView({ behavior: "smooth" }); }}>
          <label>GDE ŽELIŠ DA BUDEŠ?<input value={location} maxLength={100} onChange={e => setLocation(e.target.value)} placeholder="Grad ili destinacija" /></label>
          <div className="ph-search-hint">Od gradskih adresa do mirnih obala.<br /><span>Pronađi mesto po svom ukusu.</span></div>
          <button className="ph-primary" type="submit">Pretraži ponudu <span>↗</span></button>
        </form>
      </section>
      <section className="ph-listings" id="ponuda" aria-busy={loading}>
        <div className="ph-section-heading"><div><p className="ph-eyebrow">PROSTORI ZA TVOJE PLANOVE</p><h2>Mesto koje ti pristaje.</h2></div><a href="/owner" className="ph-outline">Dodaj svoju nekretninu</a></div>
        {(query || offer) && <div className="ph-active-filters" aria-label="Aktivni filteri">{query && <button onClick={() => search("", offer)} aria-label={`Ukloni lokaciju ${query}`}>⌖ {query} <span>×</span></button>}{offer && <button onClick={() => search(query, "")} aria-label="Ukloni vrstu ponude">{offerLabels[offer]} <span>×</span></button>}<button className="ph-clear-filters" onClick={() => search("", "")}>Obriši filtere</button></div>}
        {loading ? <><p role="status" className="ph-demo">Učitavanje oglasa…</p><div className="ph-grid" aria-hidden="true">{[0, 1, 2].map(item => <div className="ph-skeleton" key={item}><div /><span /><span /><span /></div>)}</div></> : error ? <div className="ph-empty" role="alert"><span className="ph-empty-icon" aria-hidden="true">↻</span><h3>Ponuda trenutno nije dostupna.</h3><p>Pokušaj ponovo za nekoliko trenutaka.</p><button className="ph-outline" onClick={() => search(query)}>Pokušaj ponovo</button></div> : <>
          <p className="ph-demo" role="status">Pronađeno oglasa: {page.total}{query ? ` · ${query}` : ""}</p>
          {favoritesError && <div className="property-save-error" role="alert">Status sačuvanih oglasa nije učitan. <button className="ph-outline" onClick={() => search(query)}>Pokušaj ponovo</button><a href="/account">Proveri prijavu</a></div>}
          <div className="ph-grid">{page.items.map(p => <PropertyCard key={p.id} property={p} saveAction={<SavePropertyButton propertyId={p.id} title={p.title} saved={favoriteIds === null ? null : favoriteIds.has(p.id)} onChange={saved => setFavoriteIds(current => { const next = new Set(current); if (saved) next.add(p.id); else next.delete(p.id); return next; })} />} />)}</div>
          {page.items.length === 0 && <div className="ph-empty"><span className="ph-empty-icon" aria-hidden="true">⌂</span><h3>Nema oglasa za ovaj izbor.</h3><p>{query || offer ? "Probaj drugu destinaciju ili ukloni filtere da proširiš pretragu." : "Ponuda tek počinje da raste. Tvoja nekretnina može biti prva."}</p>{query || offer ? <button className="ph-outline" onClick={() => search("", "")}>Prikaži sve oglase</button> : <a className="ph-primary" href="/owner">Objavi prvi oglas ↗</a>}</div>}
          {(offset > 0 || page.has_next) && <nav className="ph-pagination" aria-label="Stranice oglasa"><button className="ph-outline" disabled={offset === 0} onClick={() => { setOffset(Math.max(0, offset - 12)); setLoading(true); }}>Prethodna</button><span>Stranica {Math.floor(offset / 12) + 1}</span><button className="ph-outline" disabled={!page.has_next} onClick={() => { setOffset(offset + 12); setLoading(true); }}>Sledeća</button></nav>}
        </>}
      </section>
      <section className="ph-destinations" id="destinacije"><div><p className="ph-eyebrow">PROMENI OKRUŽENJE</p><h2>Gde te vodi sledeći plan?</h2><p>Gradski ritam, planinska tišina ili dani uz more.</p></div><div className="ph-destination-links">{["Beograd", "Novi Sad", "Zlatibor", "Budva"].map(city => <a href="#ponuda" key={city} onClick={() => search(city, "")}>{city}<span>↗</span></a>)}</div></section>
      <section className="ph-owner-invite"><div><p className="ph-eyebrow">IMAŠ PROSTOR ZA NEČIJE PLANOVE?</p><h2>Svaki dom ima svoju priču.<br />Podeli svoju.</h2><p>Predstavi nekretninu, odredi cenu i poveži se sa budućim gostima ili kupcima.</p></div><a href="/owner" className="ph-primary">Kreiraj svoj oglas <span>↗</span></a></section>
    </main>
    <footer className="ph-footer"><span className="ph-brand">bookica.</span><p>Mesto za odmor. Prostor za život.</p><a href="/booking">Postojeći sistem rezervacija ↗</a></footer>
  </div>;
}
