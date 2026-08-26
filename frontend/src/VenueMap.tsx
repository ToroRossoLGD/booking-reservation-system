import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Venue } from "./types";

const TILE_URL =
  import.meta.env.VITE_MAP_TILE_URL ??
  "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

export function VenueMap({
  venues,
  onSelect,
}: {
  venues: Venue[];
  onSelect: (venue: Venue) => void;
}) {
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!element.current) return;
    const map = L.map(element.current, { scrollWheelZoom: false });
    L.tileLayer(TILE_URL, {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
    }).addTo(map);
    const bounds = L.latLngBounds([]);
    venues
      .filter((venue) => venue.latitude != null && venue.longitude != null)
      .forEach((venue) => {
        const point = L.latLng(venue.latitude!, venue.longitude!);
        bounds.extend(point);
        L.marker(point)
          .addTo(map)
          .bindTooltip(venue.name)
          .on("click", () => onSelect(venue));
      });
    if (bounds.isValid()) map.fitBounds(bounds.pad(0.2), { maxZoom: 14 });
    else map.setView([44.8125, 20.4612], 11);
    window.setTimeout(() => map.invalidateSize(), 0);
    return () => {
      map.remove();
    };
  }, [venues, onSelect]);
  return <div className="venue-map" ref={element} aria-label="Map of venues" />;
}
