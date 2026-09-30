import type { SeasonalRate } from "./seasonal-rates";
import { displayDate, stayMoney } from "./stay-types";
import "./seasonal-rates.css";

export default function SeasonalRateSummary({ rates, currency }: { rates?: SeasonalRate[]; currency: string }) {
  if (!rates?.length) return null;
  return <details className="seasonal-summary"><summary>Sezonske cene ({rates.length})</summary><p>Van navedenih perioda važi osnovna cena. Završni datum nije uključen. Konačan obračun dobijaš za izabrane datume.</p><ul>{rates.map(rate => <li key={rate.start}>{rate.label && <strong>{rate.label}: </strong>}{displayDate(rate.start)} – {displayDate(rate.end)} · {stayMoney(rate.price_cents, currency)} / noć</li>)}</ul></details>;
}
