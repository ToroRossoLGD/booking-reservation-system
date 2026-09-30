import { useRef, useState } from "react";
import type { SeasonalRate } from "./seasonal-rates";
import "./seasonal-rates.css";

export default function SeasonalRateFields({ rates }: { rates: SeasonalRate[] }) {
  const [rows, setRows] = useState(() => rates.map((rate, key) => ({ ...rate, key })));
  const nextKey = useRef(rates.length);
  return <section className="seasonal-editor ph-form-wide" aria-label="Sezonski cenovnik">
    <h3>Sezonske cene noćenja</h3>
    <p>Iznosi su u valuti oglasa. Van ovih perioda važi osnovna cena. Završni datum nije uključen; periodi ne smeju da se preklapaju. Izmene važe za nove rezervacije.</p>
    {rows.map((row, index) => <fieldset className="seasonal-row" key={row.key}><legend>Period {index + 1}</legend>
      <label>Naziv perioda<input name="season_label" maxLength={80} defaultValue={row.label} placeholder="Na primer: letnja sezona" /></label>
      <label>Prva noć<input name="season_start" type="date" required defaultValue={row.start} /></label>
      <label>Do datuma (nije uključen)<input name="season_end" type="date" required defaultValue={row.end} /></label>
      <label>Sezonska cena po noći<input name="season_price" type="number" min="0.01" max="10000000000" step="0.01" required defaultValue={row.price_cents ? row.price_cents / 100 : ""} /></label>
      <button type="button" className="ph-outline" onClick={() => setRows(current => current.filter(item => item.key !== row.key))} aria-label={`Ukloni period ${index + 1}`}>Ukloni period</button>
    </fieldset>)}
    <button type="button" className="ph-outline" disabled={rows.length >= 24} onClick={() => { const key = nextKey.current++; setRows(current => [...current, { key, start: "", end: "", price_cents: 0, label: "" }]); }}>Dodaj sezonski period</button>
    <small>Najviše 24 perioda po oglasu. Sačuvaj oglas da primeniš izmene.</small>
  </section>;
}
