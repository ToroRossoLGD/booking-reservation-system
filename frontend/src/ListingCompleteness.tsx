import type { PropertyListing, OfferType } from "./property-types";
import "./listing-completeness.css";

export default function ListingCompleteness({ listing, fields, type, busy, onPhotos }: {
  listing: PropertyListing | null; fields: FormData | null; type: OfferType; busy: boolean; onPhotos: () => void;
}) {
  function value(name: string, saved?: unknown) {
    return fields ? String(fields.get(name) ?? "").trim() : String(saved ?? "").trim();
  }
  const hints: { label: string; field: string }[] = [];
  if (value("description", listing?.description).length < 20) hints.push({ label: "Dodaj opis od najmanje 20 znakova", field: "description" });
  if (!value("contact_email", listing?.contact_email)) hints.push({ label: "Dodaj kontakt email adresu", field: "contact_email" });
  const details = [
    ["property_type", "Navedi tip nekretnine"], ["neighborhood", "Dodaj naselje"],
    ["heating", "Navedi grejanje"], ["furnishing", "Navedi nameštenost"],
  ] as const;
  for (const [field, label] of details) if (!value(field, listing?.[field])) hints.push({ label, field });
  if (type === "long_term") {
    const terms = [
      ["deposit", listing?.deposit_cents, "Navedi depozit (0 ako ga nema)"],
      ["monthly_bills", listing?.monthly_bills_cents, "Navedi okvirne mesečne troškove (0 ako ih nema)"],
      ["available_from", listing?.available_from, "Navedi kada je stan dostupan"],
      ["minimum_rental_months", listing?.minimum_rental_months, "Navedi minimalno trajanje najma"],
      ["pets_policy", listing?.pets_policy, "Navedi pravilo za ljubimce"],
    ] as const;
    for (const [field, saved, label] of terms) if (!value(field, saved)) hints.push({ label, field });
  }
  const needsPhotos = !listing?.photos?.length;
  return <aside className="listing-completeness" aria-label="Preporuke za oglas">
    <h4>Dopuni oglas</h4>
    <p>Preporuke prate unos u formi. Izmene sačuvaj dugmetom „Sačuvaj oglas“. Ove preporuke ne uvode dodatne uslove za objavljivanje.</p>
    {!hints.length && !needsPhotos ? <p>Popunjeni su svi preporučeni podaci i dodate su fotografije.</p> : <ul>
      {needsPhotos && <li>{listing ? <button type="button" disabled={busy} onClick={onPhotos}>Dodaj fotografije</button> : "Fotografije dodaješ nakon prvog čuvanja oglasa."}</li>}
      {hints.map(hint => <li key={hint.field}><button type="button" disabled={busy} onClick={event => {
        const field = event.currentTarget.form?.elements.namedItem(hint.field);
        if (field instanceof HTMLElement) field.focus();
      }}>{hint.label}</button></li>)}
    </ul>}
  </aside>;
}
