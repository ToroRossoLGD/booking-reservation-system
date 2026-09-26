export type OfferType = "short_stay" | "long_term" | "sale";

export type PropertySearchFilters = {
  check_in?: string;
  check_out?: string;
  guests?: number;
  currency?: "EUR" | "RSD" | "USD";
  min_price_cents?: number;
  max_price_cents?: number;
  min_area_sqm?: number;
  max_area_sqm?: number;
  rooms?: number;
  sort?: "newest" | "price_asc" | "price_desc" | "area_desc";
};
export type PropertyInput = {
  venue_id: number;
  title: string;
  description: string;
  city: string;
  offer_type: OfferType;
  area_sqm: number;
  rooms: number;
  price_cents: number;
  currency: "EUR" | "RSD" | "USD";
  contact_email: string;
  is_published: boolean;
  booking_enabled?: boolean;
  max_guests?: number;
  minimum_nights?: number;
  timezone?: string;
  check_in_time?: string | null;
  check_out_time?: string | null;
};
export type PropertyPhoto = { id: number; property_id: number; position: number; width: number; height: number };
export type PropertyListing = PropertyInput & { id: number; photos?: PropertyPhoto[] };
export type PropertyPage = { items: PropertyListing[]; total: number; offset: number; limit: number; has_next: boolean };
export const offerLabels: Record<OfferType, string> = { short_stay: "Stan na dan", long_term: "Dugoročni najam", sale: "Prodaja" };
export const priceUnits: Record<OfferType, string> = { short_stay: "noć", long_term: "mesec", sale: "ukupno" };
export function propertyPrice(property: PropertyInput) {
  return new Intl.NumberFormat("sr-Latn", { style: "currency", currency: property.currency, maximumFractionDigits: 2 }).format(property.price_cents / 100);
}
