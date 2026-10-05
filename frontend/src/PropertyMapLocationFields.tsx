import { lazy, Suspense, useState } from "react";
import type { PropertyInput } from "./property-types";
import "./property-map.css";
const PropertyMap = lazy(() => import("./PropertyMap"));

export default function PropertyMapLocationFields({ value }: { value: PropertyInput | null }) {
  const [enabled, setEnabled] = useState(value?.map_latitude != null && value?.map_longitude != null);
  const [latitude, setLatitude] = useState(String(value?.map_latitude ?? ""));
  const [longitude, setLongitude] = useState(String(value?.map_longitude ?? ""));
  const [showMap, setShowMap] = useState(false);
  const valid = latitude !== "" && longitude !== "" && Number.isFinite(Number(latitude)) && Number.isFinite(Number(longitude)) && Math.abs(Number(latitude)) <= 85 && Math.abs(Number(longitude)) <= 180;
  return <section className="property-map-location" aria-label="Lokacija na mapi">
    <h3>Približna lokacija</h3>
    <label><input type="checkbox" name="map_enabled" checked={enabled} onChange={event => setEnabled(event.target.checked)} />Prikaži približnu lokaciju na javnoj mapi</label>
    <p>Lokacija je opciona. Čuvamo i objavljujemo koordinate zaokružene na dve decimale (područje približno jednog kilometra). Tačnu adresu dogovori privatno. Isključivanjem i čuvanjem oglasa uklanjaš lokaciju iz Bookicine mape.</p>
    {enabled && <>
      <button className="ph-outline" type="button" aria-expanded={showMap} onClick={() => setShowMap(!showMap)}>{showMap ? "Sakrij izbor na mapi" : "Izaberi lokaciju na mapi"}</button>
      <p><small>Otvaranjem mape učitava se podloga sa OpenStreetMap servisa.</small></p>
      {showMap && <Suspense fallback={<p role="status">Učitavanje mape…</p>}><PropertyMap point={valid ? [Number(latitude), Number(longitude)] : undefined} onPick={point => { setLatitude(String(point[0])); setLongitude(String(point[1])); }} /></Suspense>}
      <div className="property-map-coordinates">
        <label>Geografska širina<input name="map_latitude" type="number" min={-85} max={85} step="any" required value={latitude} onChange={event => setLatitude(event.target.value)} /></label>
        <label>Geografska dužina<input name="map_longitude" type="number" min={-180} max={180} step="any" required value={longitude} onChange={event => setLongitude(event.target.value)} /></label>
      </div>
    </>}
  </section>;
}
