import type { RentalTerms } from "./rental-terms";
import { petsLabels } from "./rental-terms";
import { displayDate, stayMoney } from "./stay-types";

export default function RentalTermsDisplay({ terms, currency, snapshot = false }: { terms: RentalTerms; currency: string; snapshot?: boolean }) {
  if ([terms.deposit_cents, terms.monthly_bills_cents, terms.available_from, terms.minimum_rental_months, terms.pets_policy].every(value => value == null)) return null;
  return <section className="rental-terms" aria-label={snapshot ? "Uslovi pri slanju upita" : "Uslovi najma"}>
    <h3>{snapshot ? "Uslovi iz oglasa pri slanju upita" : "Uslovi najma"}</h3>
    <ul>
      {terms.deposit_cents != null && <li>Depozit: {terms.deposit_cents === 0 ? "Bez depozita" : stayMoney(terms.deposit_cents, currency)}</li>}
      {terms.monthly_bills_cents != null && <li>Okvirni mesečni troškovi: {stayMoney(terms.monthly_bills_cents, currency)}</li>}
      {terms.available_from && <li>Dostupno od: {displayDate(terms.available_from)}</li>}
      {terms.minimum_rental_months != null && <li>Minimalno trajanje najma: {terms.minimum_rental_months} meseci</li>}
      {terms.pets_policy && <li>Ljubimci: {petsLabels[terms.pets_policy]}</li>}
    </ul>
  </section>;
}
