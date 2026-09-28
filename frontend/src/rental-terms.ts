export interface RentalTerms {
  deposit_cents?: number | null;
  monthly_bills_cents?: number | null;
  available_from?: string | null;
  minimum_rental_months?: number | null;
  pets_policy?: "allowed" | "not_allowed" | "by_agreement" | null;
}
export const petsLabels = { allowed: "Dozvoljeni", not_allowed: "Nisu dozvoljeni", by_agreement: "Po dogovoru" };
export function readRentalTerms(fields: FormData, enabled: boolean): RentalTerms {
  const number = (name: string) => enabled && fields.get(name) !== null && fields.get(name) !== "" ? Number(fields.get(name)) : null;
  const deposit = number("deposit");
  const bills = number("monthly_bills");
  return {
    deposit_cents: deposit === null ? null : Math.round(deposit * 100),
    monthly_bills_cents: bills === null ? null : Math.round(bills * 100),
    available_from: enabled ? String(fields.get("available_from") ?? "") || null : null,
    minimum_rental_months: number("minimum_rental_months"),
    pets_policy: enabled ? (String(fields.get("pets_policy") ?? "") || null) as RentalTerms["pets_policy"] : null,
  };
}
