import SeasonalRateSummary from "./SeasonalRateSummary";
import { useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { PropertyListing, PropertyPhoto } from "./property-types";
import { offerLabels, priceUnits, propertyPrice } from "./property-types";
import { OwnerPhoto } from "./PropertyPhotoManager";
import PropertyFacts from "./PropertyFacts";
import RentalTermsDisplay from "./RentalTermsDisplay";
import StayTimes from "./StayTimes";
import "./property-home.css";
import "./property-detail.css";
import "./rentals.css";

export default function OwnerPropertyPreview({ id }: { id: string }) {
  const valid = /^[1-9]\d*$/.test(id) && Number.isSafeInteger(Number(id));
  const [property, setProperty] = useState<PropertyListing | null>(null);
  const [photos, setPhotos] = useState<PropertyPhoto[] | null>(null);
  const [photoError, setPhotoError] = useState(false);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  useEffect(() => {
    if (!valid) return;
    const controller = new AbortController();
    api.ownerProperty(Number(id), controller.signal).then(listing => {
      if (controller.signal.aborted) return;
      setProperty(listing);
      api.ownerPhotos(listing.id).then(items => { if (!controller.signal.aborted) setPhotos(items); })
        .catch(() => { if (!controller.signal.aborted) setPhotoError(true); });
    }).catch(err => {
      if (!controller.signal.aborted) setError(err instanceof ApiError && [401, 403, 404].includes(err.status) ? "Prijavi se kao vlasnik ovog oglasa. Oglas možda nije dostupan." : "Pregled nije učitan. Pokušaj ponovo.");
    });
    return () => controller.abort();
  }, [id, valid, version]);
  function reload() { setError(""); setPhotoError(false); setPhotos(null); setProperty(null); setVersion(value => value + 1); }
  return <div className="property-home property-detail-page"><main>
    <a href="/owner" className="ph-text-link">← Nazad na tvoje oglase</a>
    <section className="rental-terms" aria-label="Privatni pregled"><h2>Privatni pregled oglasa</h2><p>Prikaz sačuvanih podataka. Za izmene se vrati u vlasnički panel. Ovaj pregled ne objavljuje oglas i ne prima rezervacije ili upite.</p></section>
    {!valid ? <p role="alert">Link oglasa nije ispravan.</p> : error ? <div role="alert"><p>{error}</p><a href="/account">Prijava</a> <button className="ph-outline" onClick={reload}>Pokušaj ponovo</button></div> : !property ? <p role="status">Učitavanje pregleda…</p> : <>
      <div className="property-detail-heading"><p>{property.is_published ? "Objavljen oglas" : "Nacrt — nije u javnoj ponudi"} · {offerLabels[property.offer_type]}</p><h1>{property.title}</h1><p>{property.city} · {property.area_sqm} m² · Broj soba: {property.rooms}</p></div>
      <div className="property-detail-layout"><section aria-label="Opis i fotografije">
        {photoError ? <p role="alert">Fotografije nisu učitane. <button onClick={reload}>Osveži pregled</button></p> : photos === null ? <p role="status">Učitavanje fotografija…</p> : photos.length ? <div className="owner-preview-photos">{photos.map(photo => <figure key={photo.id}><OwnerPhoto photo={photo} /><figcaption>{photo.position === 0 ? "Naslovna fotografija" : `Fotografija ${photo.position + 1}`}</figcaption></figure>)}</div> : <p>Fotografije još nisu dodate.</p>}
        <h2>O nekretnini</h2><p className="ph-description">{property.description}</p><PropertyFacts property={property} />
      </section><aside className="property-detail-actions" aria-label="Cena i uslovi">
        <p className="property-detail-price"><strong>{propertyPrice(property)}</strong> / {priceUnits[property.offer_type]}</p>
        <p>Javni kontakt: {property.contact_email}</p>
        {property.offer_type === "long_term" && <RentalTermsDisplay terms={property} currency={property.currency} />}
        {property.offer_type === "short_stay" && <><p>{property.booking_enabled ? "Rezervacije uključene" : "Rezervacije isključene"}</p><p>Do {property.max_guests ?? 2} gostiju · {property.minimum_nights ?? 1}–{property.maximum_nights ?? 90} noćenja</p><p>Najava dolaska: {property.advance_notice_days ?? 1} dana. Rok odlaska: {property.booking_window_days ?? 365} dana unapred.</p><StayTimes {...property} /><SeasonalRateSummary rates={property.seasonal_rates} currency={property.currency} /></>}
      </aside></div>
    </>}
  </main></div>;
}
