import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { PropertyListing, PropertySearchFilters } from "./property-types";
import { offerLabels, priceUnits, propertyPrice } from "./property-types";
import type { StayDates } from "./stay-types";
import "./property-map.css";

export type MapBounds = Required<Pick<PropertySearchFilters, "map_south" | "map_north" | "map_west" | "map_east">>;
type Props = { items?: PropertyListing[]; bounds?: MapBounds; busy?: boolean; onSearch?: (bounds: MapBounds) => void; point?: [number, number]; onPick?: (point: [number, number]) => void; stayDates?: StayDates };
const noItems: PropertyListing[] = [];

export default function PropertyMap({ items = noItems, bounds, busy, onSearch, point, onPick, stayDates }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const fitted = useRef(false);
  const [tileError, setTileError] = useState(false);
  const [tileVersion, setTileVersion] = useState(0);
  useEffect(() => {
    if (!container.current) return;
    const instance = L.map(container.current, { minZoom: 2, maxZoom: 15, scrollWheelZoom: false, maxBounds: [[-85, -180], [85, 180]], maxBoundsViscosity: 1 }).setView([44.8, 20.46], 7);
    map.current = instance; fitted.current = false;
    const observer = new ResizeObserver(() => instance.invalidateSize());
    observer.observe(container.current);
    return () => { observer.disconnect(); instance.remove(); map.current = null; };
  }, []);
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, noWrap: true, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>' });
    tiles.on("tileerror", () => setTileError(true));
    tiles.addTo(instance);
    return () => { tiles.off(); tiles.remove(); };
  }, [tileVersion]);
  const south = bounds?.map_south, north = bounds?.map_north, west = bounds?.map_west, east = bounds?.map_east;
  useEffect(() => {
    if (south !== undefined && north !== undefined && west !== undefined && east !== undefined) {
      map.current?.fitBounds([[south, west], [north, east]], { animate: false });
      fitted.current = true;
    }
  }, [south, north, west, east]);
  useEffect(() => {
    const instance = map.current;
    if (!instance || !onPick) return;
    const pick = (event: L.LeafletMouseEvent) => onPick([Number(event.latlng.lat.toFixed(2)), Number(event.latlng.lng.toFixed(2))]);
    instance.on("click", pick);
    return () => { instance.off("click", pick); };
  }, [onPick]);
  const latitude = point?.[0], longitude = point?.[1];
  const stayQuery = stayDates ? `?${new URLSearchParams({ ...stayDates, guests: String(stayDates.guests) })}` : "";
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const layer = L.layerGroup().addTo(instance);
    const positions: L.LatLngTuple[] = [];
    const groups = new Map<string, PropertyListing[]>();
    for (const item of items) {
      if (item.map_latitude == null || item.map_longitude == null) continue;
      const key = `${item.map_latitude},${item.map_longitude}`;
      groups.set(key, [...(groups.get(key) ?? []), item]);
    }
    for (const group of groups.values()) {
      const position: L.LatLngTuple = [group[0].map_latitude!, group[0].map_longitude!];
      positions.push(position);
      const popup = document.createElement("div");
      for (const item of group) {
        const link = document.createElement("a");
        link.href = `/properties/${item.id}${stayQuery}`; link.textContent = item.title;
        const price = document.createElement("p");
        price.textContent = `${offerLabels[item.offer_type]} · ${item.stay_total_cents != null ? `${propertyPrice({ ...item, price_cents: item.stay_total_cents })} ukupno za boravak` : `${propertyPrice(item)} / ${priceUnits[item.offer_type]}${item.seasonal_rates?.length ? " · Osnovna cena" : ""}`}`;
        popup.append(link, price);
      }
      const note = document.createElement("p"); note.textContent = "Približna lokacija, nije tačna adresa."; popup.append(note);
      const icon = L.divIcon({ className: "property-map-pin", html: `<span>${group.length > 1 ? group.length : "⌂"}</span>`, iconSize: [36, 36], iconAnchor: [18, 18] });
      L.marker(position, { icon, title: `Približna lokacija: ${group.map(item => item.title).join(", ")}`, alt: "Otvori oglase na ovoj lokaciji", keyboard: true }).bindPopup(popup).addTo(layer);
    }
    if (latitude !== undefined && longitude !== undefined) {
      positions.push([latitude, longitude]);
      L.circle([latitude, longitude], { radius: 700, color: "#164f3c" }).addTo(layer);
      instance.setView([latitude, longitude], 13, { animate: false });
    } else if (!fitted.current && positions.length) {
      instance.fitBounds(positions, { maxZoom: 12, padding: [30, 30], animate: false }); fitted.current = true;
    }
    return () => { layer.remove(); };
  }, [items, latitude, longitude, stayQuery]);
  function searchArea() {
    const area = map.current?.getBounds();
    if (!area || !onSearch) return;
    onSearch({ map_south: Math.max(-85, area.getSouth()), map_north: Math.min(85, area.getNorth()), map_west: Math.max(-180, area.getWest()), map_east: Math.min(180, area.getEast()) });
  }
  function showResults() {
    const points = items.filter(item => item.map_latitude != null && item.map_longitude != null).map(item => [item.map_latitude!, item.map_longitude!] as L.LatLngTuple);
    if (points.length) map.current?.fitBounds(points, { maxZoom: 12, padding: [30, 30] });
  }
  return <section className="property-map-panel" aria-label={onPick ? "Izbor približne lokacije" : "Mapa nekretnina"}>
    <p>{onPick ? "Klikni na mapu ili unesi koordinate ispod. Izaberi približno područje nekretnine." : "Prikazane su približne lokacije oglasa sa trenutne stranice rezultata. Za ostale oglase koristi paginaciju ispod liste."}</p>
    <div className="property-map-canvas" ref={container} aria-label="Interaktivna mapa" />
    {tileError && <p role="alert">Podloga mape nije dostupna. Lista oglasa i dalje radi. <button type="button" onClick={() => { setTileError(false); setTileVersion(value => value + 1); }}>Ponovo učitaj mapu</button></p>}
    {onSearch && <div className="property-map-actions"><button type="button" className="ph-outline" disabled={busy} onClick={searchArea}>Pretraži ovaj deo mape</button><button type="button" className="ph-outline" disabled={busy || !items.some(item => item.map_latitude != null)} onClick={showResults}>Prikaži lokacije ove stranice</button></div>}
    <p><small>Približna lokacija nije tačna adresa. Podloga: OpenStreetMap. <a href="https://www.openstreetmap.org/fixthemap" target="_blank" rel="noreferrer">Prijavi grešku na podlozi</a></small></p>
  </section>;
}
