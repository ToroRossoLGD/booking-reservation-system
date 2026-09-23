import { useState } from "react";
import type { ReactNode } from "react";
import StayBooking from "./StayBooking";
import RentalInquiryForm from "./RentalInquiryForm";
import PropertyGallery from "./PropertyGallery";
import { offerLabels, priceUnits, propertyPrice } from "./property-types";
import type { PropertyListing } from "./property-types";

export default function PropertyCard({ property: p, saveAction }: { property: PropertyListing; saveAction?: ReactNode }) {
  const [expanded, setExpanded] = useState(false);
  return <article className="ph-card">
    {p.photos?.length ? <div className="property-photo-card"><PropertyGallery key={p.photos.map(photo => photo.id).join(",")} photos={p.photos} title={p.title} /><span className="ph-tag">{offerLabels[p.offer_type]}</span></div> : <div className={`ph-card-art ph-scene-${p.offer_type === "short_stay" ? "sea" : "city"}`}>
      <span className="ph-tag">{offerLabels[p.offer_type]}</span>
      <div className="ph-mini-house" aria-hidden="true"><i /><i /><i /></div>
      <span className="ph-art-label">Ilustracija nekretnine</span>
    </div>}
    <div className="ph-card-body">
      {saveAction}
      <p className="ph-location"><span aria-hidden="true">⌖</span> {p.city}</p><h3>{p.title}</h3>
      {!expanded && <p className="ph-card-preview">{p.description}</p>}
      <p className="ph-facts">{p.area_sqm} m² <span>·</span> {p.rooms === 0 ? "Garsonjera" : `Broj soba: ${p.rooms}`}</p>
      <div className="ph-card-bottom"><p><strong>{propertyPrice(p)}</strong> / {priceUnits[p.offer_type]}</p>
        <button aria-expanded={expanded} aria-controls={`property-${p.id}`} onClick={() => setExpanded(!expanded)} aria-label={`Detalji: ${p.title}`}>{expanded ? "Zatvori −" : "Detalji ↗"}</button>
      </div>
      <div id={`property-${p.id}`} className="ph-detail" hidden={!expanded}>
        <p className="ph-description">{p.description}</p>
        {p.offer_type === "long_term" && expanded && <RentalInquiryForm property={p} />}
        {p.offer_type === "short_stay" && (p.booking_enabled ? expanded && <StayBooking property={p} /> : <p>Za dostupnost i cenu kontaktiraj domaćina. Online rezervacije za ovaj smeštaj nisu uključene.</p>)}
        <a className="ph-outline" href={`mailto:${encodeURIComponent(p.contact_email)}?subject=${encodeURIComponent(`Upit za nekretninu: ${p.title}`)}`}>Kontaktiraj vlasnika ↗</a>
      </div>
    </div>
  </article>;
}
