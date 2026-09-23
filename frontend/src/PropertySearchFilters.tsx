import { useState } from "react";
import type { OfferType, PropertySearchFilters as Filters } from "./property-types";
import { priceUnits } from "./property-types";
import "./property-search.css";

export default function PropertySearchFilters({ offer, value, onApply }: {
  offer: OfferType | ""; value: Filters; onApply: (filters: Filters) => void;
}) {
  const [minPrice, setMinPrice] = useState(value.min_price_cents === undefined ? "" : String(value.min_price_cents / 100));
  const [maxPrice, setMaxPrice] = useState(value.max_price_cents === undefined ? "" : String(value.max_price_cents / 100));
  const [minArea, setMinArea] = useState(String(value.min_area_sqm ?? ""));
  const [maxArea, setMaxArea] = useState(String(value.max_area_sqm ?? ""));
  const [rooms, setRooms] = useState(String(value.rooms ?? ""));
  const [currency, setCurrency] = useState<"EUR" | "RSD" | "USD">(value.currency ?? "EUR");
  const [sort, setSort] = useState<Filters["sort"]>(value.sort ?? "newest");
  const [error, setError] = useState("");

  return <details className="ph-filter-panel">
    <summary>Napredni filteri i sortiranje</summary>
    <form aria-label="Napredna pretraga" onSubmit={event => {
      event.preventDefault();
      if ((minPrice !== "" && maxPrice !== "" && Number(minPrice) > Number(maxPrice)) ||
        (minArea !== "" && maxArea !== "" && Number(minArea) > Number(maxArea))) {
        setError("Minimalna vrednost ne može biti veća od maksimalne."); return;
      }
      setError("");
      const filters: Filters = { sort };
      if (minArea !== "") filters.min_area_sqm = Number(minArea);
      if (maxArea !== "") filters.max_area_sqm = Number(maxArea);
      if (rooms !== "") filters.rooms = Number(rooms);
      if (offer && (minPrice !== "" || maxPrice !== "" || sort?.startsWith("price_"))) {
        filters.currency = currency;
        if (minPrice !== "") filters.min_price_cents = Math.round(Number(minPrice) * 100);
        if (maxPrice !== "") filters.max_price_cents = Math.round(Number(maxPrice) * 100);
      }
      onApply(filters);
    }}>
      <p className="ph-filter-help">{offer ? `Cena po jedinici: ${priceUnits[offer]}.` : "Za pretragu po ceni prvo izaberi vrstu ponude iznad."}</p>
      <label>Cena od<input type="number" min="0" max="10000000000" step="0.01" disabled={!offer} value={minPrice} onChange={e => setMinPrice(e.target.value)} /></label>
      <label>Cena do<input type="number" min="0" max="10000000000" step="0.01" disabled={!offer} value={maxPrice} onChange={e => setMaxPrice(e.target.value)} /></label>
      <label>Valuta<select disabled={!offer} value={currency} onChange={e => setCurrency(e.target.value as typeof currency)}><option>EUR</option><option>RSD</option><option>USD</option></select></label>
      <label>Kvadratura od (m²)<input type="number" min="1" max="100000" step="1" value={minArea} onChange={e => setMinArea(e.target.value)} /></label>
      <label>Kvadratura do (m²)<input type="number" min="1" max="100000" step="1" value={maxArea} onChange={e => setMaxArea(e.target.value)} /></label>
      <label>Broj soba<input type="number" min="0" max="100" step="1" value={rooms} onChange={e => setRooms(e.target.value)} /><small>Tačan broj; 0 = garsonjera.</small></label>
      <label>Sortiranje<select value={sort} onChange={e => setSort(e.target.value as Filters["sort"])}><option value="newest">Najnoviji oglasi</option><option value="price_asc" disabled={!offer}>Cena: od niže ka višoj</option><option value="price_desc" disabled={!offer}>Cena: od više ka nižoj</option><option value="area_desc">Najveća kvadratura</option></select></label>
      {error && <p role="alert" className="ph-filter-help">{error}</p>}
      <button type="submit" className="ph-primary">Primeni filtere</button>
    </form>
  </details>;
}
