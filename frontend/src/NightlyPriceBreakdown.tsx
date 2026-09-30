import type { NightlyPrice } from "./stay-types";
import { displayDate, stayMoney } from "./stay-types";
import "./seasonal-rates.css";

export default function NightlyPriceBreakdown({ prices, currency }: { prices?: NightlyPrice[] | null; currency: string }) {
  if (!prices?.length) return null;
  return <details className="nightly-breakdown"><summary>Obračun po noćima ({prices.length})</summary><div className="nightly-breakdown-scroll" tabIndex={0} aria-label="Cene po datumima"><table><caption>Cena za svaku noć boravka</caption><thead><tr><th scope="col">Noć od</th><th scope="col">Cena</th></tr></thead><tbody>{prices.map(night => <tr key={night.date}><th scope="row">{displayDate(night.date)}</th><td>{stayMoney(night.price_cents, currency)}</td></tr>)}</tbody></table></div></details>;
}
