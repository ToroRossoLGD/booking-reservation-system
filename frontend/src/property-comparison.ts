import type { PropertyListing } from "./property-types";

export function comparisonRestriction(items: PropertyListing[], property: PropertyListing) {
  if (items.some(item => item.id === property.id)) return "";
  if (items.length >= 3) return "Možeš porediti najviše tri oglasa. Ukloni neki iz izbora.";
  if (items.length && (items[0].offer_type !== property.offer_type || items[0].currency !== property.currency)) return "Izaberi oglase iste vrste ponude i valute ili očisti poređenje.";
  return "";
}

