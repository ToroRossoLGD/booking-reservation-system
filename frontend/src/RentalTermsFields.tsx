import type { RentalTerms } from "./rental-terms";
import { petsLabels } from "./rental-terms";

export default function RentalTermsFields({ value }: { value: RentalTerms }) {
  return <>
    <h3 className="ph-form-wide">Uslovi dugoročnog najma</h3>
    <small className="ph-form-wide">Opciona polja. Iznosi su u valuti oglasa. Unesi 0 ako nema depozita ili dodatnih troškova. Izmene važe za nove upite.</small>
    <label>Depozit<input name="deposit" type="number" min="0" max="10000000000" step="0.01" defaultValue={value.deposit_cents == null ? "" : value.deposit_cents / 100} /></label>
    <label>Okvirni mesečni troškovi<input name="monthly_bills" type="number" min="0" max="10000000000" step="0.01" defaultValue={value.monthly_bills_cents == null ? "" : value.monthly_bills_cents / 100} /></label>
    <label>Dostupno od<input name="available_from" type="date" defaultValue={value.available_from ?? ""} /></label>
    <label>Minimalno trajanje najma (meseci)<input name="minimum_rental_months" type="number" min="1" max="120" defaultValue={value.minimum_rental_months ?? ""} /></label>
    <label>Ljubimci<select name="pets_policy" defaultValue={value.pets_policy ?? ""}><option value="">Nije navedeno</option>{Object.entries(petsLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
  </>;
}
