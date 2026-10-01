import { useState } from "react";
import { detailEntries, detailKeys, detailLabels } from "./property-details";
import { petsLabels } from "./rental-terms";
import { offerLabels, priceUnits, propertyPrice } from "./property-types";
import type { PropertyListing } from "./property-types";
import "./property-comparison.css";

export default function PropertyComparison({ items, onRemove, onClear }: {
  items: PropertyListing[]; onRemove: (id: number) => void; onClear: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  if (!items.length) return null;
  const type = items[0].offer_type;
  const unknown = "Nije navedeno";
  const rows: [string, (p: PropertyListing) => string | number][] = [
    ["Grad", p => p.city],
    [type === "short_stay" ? "Osnovna cena / noć" : `Cena / ${priceUnits[type]}`, p => propertyPrice(p)],
    ["Površina", p => `${p.area_sqm} m²`], ["Broj soba", p => p.rooms === 0 ? "Garsonjera" : p.rooms],
    ...detailKeys.map(key => [detailLabels[key], (p: PropertyListing) => detailEntries(p).find(([label]) => label === detailLabels[key])?.[1] ?? unknown] as [string, (p: PropertyListing) => string]),
  ];
  if (type === "long_term") rows.push(
    ["Depozit", p => p.deposit_cents == null ? unknown : propertyPrice({ ...p, price_cents: p.deposit_cents })],
    ["Okvirni mesečni troškovi", p => p.monthly_bills_cents == null ? unknown : propertyPrice({ ...p, price_cents: p.monthly_bills_cents })],
    ["Dostupno od", p => p.available_from ?? unknown],
    ["Minimalni najam (meseci)", p => p.minimum_rental_months ?? unknown],
    ["Ljubimci", p => p.pets_policy ? petsLabels[p.pets_policy] : unknown],
  );
  if (type === "short_stay") rows.push(
    ["Rezervacije u aplikaciji", p => p.booking_enabled ? "Da" : "Ne"],
    ["Maksimalno gostiju", p => p.max_guests ?? unknown],
    ["Minimum noćenja", p => p.minimum_nights ?? unknown],
    ["Podešena pauza za pripremu (dana)", p => p.preparation_days ?? 0],
    ["Maksimum noćenja", p => p.maximum_nights ?? unknown],
    ["Najava dolaska (dana)", p => p.advance_notice_days ?? 1],
    ["Rok odlaska (dana unapred)", p => p.booking_window_days ?? 365],
    ["Prijava od", p => p.check_in_time ?? "Po dogovoru"],
    ["Odjava do", p => p.check_out_time ?? "Po dogovoru"],
  );
  return <section className="property-comparison" aria-label="Poređenje oglasa">
    <h2>Poređenje oglasa ({items.length}/3)</h2>
    <p>{offerLabels[type]} · {items[0].currency}. Izbor ostaje tokom pretrage; osvežavanje stranice ga briše.</p>
    <ul>{items.map(p => <li key={p.id}>{p.title} <button type="button" onClick={() => onRemove(p.id)} aria-label={`Ukloni iz poređenja: ${p.title}`}>Ukloni</button></li>)}</ul>
    <button type="button" disabled={items.length < 2} aria-expanded={expanded && items.length >= 2} aria-controls="property-comparison-table" onClick={() => setExpanded(value => !value)}>{expanded ? "Sakrij poređenje" : "Prikaži poređenje"}</button>{" "}
    <button type="button" onClick={() => { setExpanded(false); onClear(); }}>Očisti poređenje</button>
    {items.length < 2 && <p>Dodaj još jedan oglas za poređenje.</p>}
    {expanded && items.length >= 2 && <div id="property-comparison-table">
      <p>Podaci su iz trenutka izbora oglasa. Aktuelne uslove proveri na stranici oglasa.{type === "short_stay" && " Prikazana je osnovna cena po noći; sezonske cene i dostupnost proveri za konkretne datume."}</p>
      <p>Na manjim ekranima pomeraj tabelu levo-desno da vidiš sve oglase.</p>
      <div className="comparison-scroll" role="region" aria-label="Tabela poređenja, pomeraj vodoravno" tabIndex={0}>
        <table><caption>Izabrane nekretnine uporedo</caption><thead><tr><th scope="col">Podatak</th>{items.map(p => <th scope="col" key={p.id}><a href={`/properties/${p.id}`}>{p.title}</a></th>)}</tr></thead>
          <tbody>{rows.map(([label, read]) => <tr key={label}><th scope="row">{label}</th>{items.map(p => <td key={p.id}>{read(p)}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </div>}
  </section>;
}
