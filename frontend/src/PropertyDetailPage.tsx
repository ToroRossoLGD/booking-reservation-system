import { useEffect, useState } from "react";
import { parseStayDates } from "./stay-types";
import { api, ApiError } from "./api";
import PropertyGallery from "./PropertyGallery";
import PropertyActions from "./PropertyActions";
import SavePropertyButton from "./SavePropertyButton";
import { offerLabels, priceUnits, propertyPrice } from "./property-types";
import type { PropertyListing } from "./property-types";
import "./property-home.css";
import "./property-refresh.css";
import "./property-detail.css";

export default function PropertyDetailPage({ id }: { id: string }) {
  const [property, setProperty] = useState<PropertyListing | null>(null);
  const [error, setError] = useState<"missing" | "network" | null>(null);
  const [retry, setRetry] = useState(0);
  const [saved, setSaved] = useState<boolean | null>(null);
  const [saveError, setSaveError] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const stayDates = parseStayDates(new URLSearchParams(window.location.search));
  const validId = /^[1-9]\d*$/.test(id) && Number.isSafeInteger(Number(id));
  const url = `${window.location.origin}/properties/${id}`;

  useEffect(() => {
    if (!validId) return;
    const controller = new AbortController();
    api.property(Number(id), controller.signal).then(async listing => {
      if (controller.signal.aborted) return;
      setProperty(listing);
      if (!localStorage.getItem("bookica_token")) { setSaved(false); return; }
      try {
        const result = await api.savedPropertyIds([listing.id], controller.signal);
        if (!controller.signal.aborted) setSaved(result.property_ids.includes(listing.id));
      } catch {
        if (!controller.signal.aborted) setSaveError(true);
      }
    }).catch(err => {
      if (!controller.signal.aborted) setError(err instanceof ApiError && err.status === 404 ? "missing" : "network");
    });
    return () => controller.abort();
  }, [id, retry, validId]);

  useEffect(() => {
    const previous = document.title;
    document.title = property ? `${property.title} | Bookica` : "Oglas | Bookica";
    return () => { document.title = previous; };
  }, [property]);

  function reload() { setProperty(null); setError(null); setSaved(null); setSaveError(false); setRetry(value => value + 1); }
  async function copyLink() {
    setCopied(false); setCopyError(false);
    try { await navigator.clipboard.writeText(url); setCopied(true); }
    catch { setCopyError(true); }
  }

  return <div className="property-home property-detail-page">
    <header className="ph-header"><a className="ph-brand" href="/">bookica.</a><nav aria-label="Navigacija oglasa"><a href="/saved">Sačuvani oglasi</a><a href="/account">Moj nalog</a></nav></header>
    <main>
      <a className="ph-text-link" href="/">← Svi oglasi</a>
      {!validId || error === "missing" ? <section className="ph-empty"><h1>Oglas nije dostupan.</h1><p>Možda je povučen ili link nije ispravan.</p></section> : error ? <section className="ph-empty" role="alert"><h1>Oglas trenutno nije učitan.</h1><button className="ph-outline" onClick={reload}>Pokušaj ponovo</button></section> : !property ? <p role="status">Učitavanje oglasa…</p> : <>
        <div className="property-detail-heading"><p className="ph-eyebrow">{offerLabels[property.offer_type]} · {property.city}</p><h1>{property.title}</h1><p>{property.area_sqm} m² · {property.rooms === 0 ? "Garsonjera" : `Broj soba: ${property.rooms}`}</p></div>
        <div className="property-detail-layout">
          <section aria-label="Opis i fotografije">
            {property.photos?.length ? <PropertyGallery photos={property.photos} title={property.title} /> : <div className="property-detail-no-photo">Fotografije još nisu dodate.</div>}
            <h2>O nekretnini</h2><p className="ph-description">{property.description}</p>
          </section>
          <aside className="property-detail-actions" aria-label="Cena i kontakt">
            <p className="property-detail-price"><strong>{propertyPrice(property)}</strong> / {priceUnits[property.offer_type]}</p>
            <SavePropertyButton propertyId={property.id} title={property.title} saved={saved} onChange={setSaved} />
            {saveError && <p role="alert">Status sačuvanog oglasa nije učitan. <button onClick={reload}>Pokušaj ponovo</button></p>}
            <div className="property-share"><button className="ph-outline" onClick={() => void copyLink()}>Kopiraj link oglasa</button>{copied && <p role="status">Link je kopiran.</p>}{copyError && <label>Kopiraj adresu ručno<input readOnly value={url} onFocus={event => event.target.select()} /></label>}</div>
            <PropertyActions property={property} stayDates={stayDates} />
          </aside>
        </div>
      </>}
    </main>
  </div>;
}
