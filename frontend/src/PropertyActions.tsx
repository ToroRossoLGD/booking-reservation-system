import StayTimes from "./StayTimes";
import type { StayDates } from "./stay-types";
import StayBooking from "./StayBooking";
import RentalInquiryForm from "./RentalInquiryForm";
import type { PropertyListing } from "./property-types";

export default function PropertyActions({ property, stayDates }: { property: PropertyListing; stayDates?: StayDates }) {
  return <>
    {property.offer_type === "short_stay" && <StayTimes {...property} />}
    {property.offer_type === "long_term" && <RentalInquiryForm property={property} />}
    {property.offer_type === "short_stay" && (property.booking_enabled ? <StayBooking property={property} initialDates={stayDates} /> : <p>Za dostupnost i cenu kontaktiraj domaćina. Online rezervacije za ovaj smeštaj nisu uključene.</p>)}
    <a className="ph-outline" href={`mailto:${encodeURIComponent(property.contact_email)}?subject=${encodeURIComponent(`Upit za nekretninu: ${property.title}`)}`}>Kontaktiraj vlasnika ↗</a>
  </>;
}
