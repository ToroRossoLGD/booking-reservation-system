import { detailEntries } from "./property-details";
import type { PropertyDetails } from "./property-details";

export default function PropertyFacts({ property }: { property: PropertyDetails }) {
  const entries = detailEntries(property);
  if (!entries.length) return null;
  return <dl className="property-facts" aria-label="Karakteristike nekretnine">{entries.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>;
}
