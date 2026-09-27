export const detailOptions = {
  property_type: { apartment: "Stan", house: "Kuća" },
  heating: { district: "Centralno / daljinsko", electric: "Na struju", gas: "Na gas", heat_pump: "Toplotna pumpa", solid_fuel: "Čvrsto gorivo", other: "Drugo" },
  furnishing: { furnished: "Namešteno", partial: "Polunamešteno", unfurnished: "Nenamešteno" },
};
export type PropertyDetails = {
  property_type?: keyof typeof detailOptions.property_type | null;
  neighborhood?: string | null;
  floor?: number | null;
  heating?: keyof typeof detailOptions.heating | null;
  furnishing?: keyof typeof detailOptions.furnishing | null;
  has_elevator?: boolean | null;
  has_parking?: boolean | null;
  has_terrace?: boolean | null;
};
export const detailLabels: Record<keyof PropertyDetails, string> = { property_type: "Tip nekretnine", neighborhood: "Naselje", floor: "Sprat", heating: "Grejanje", furnishing: "Nameštenost", has_elevator: "Lift", has_parking: "Parking", has_terrace: "Terasa" };
export const detailKeys = Object.keys(detailLabels) as (keyof PropertyDetails)[];

export function readDetails(fields: FormData): PropertyDetails {
  const data: Record<string, unknown> = {};
  for (const key of detailKeys) {
    const value = String(fields.get(key) ?? "").trim();
    data[key] = value === "" ? null : key === "floor" ? Number(value) : key.startsWith("has_") ? value === "true" : value;
  }
  return data as PropertyDetails;
}

export function detailEntries(details: PropertyDetails) {
  return detailKeys.flatMap(key => {
    const value = details[key];
    if (value === undefined || value === null || value === "") return [];
    const label = typeof value === "boolean" ? (value ? "Da" : "Ne") : key === "floor" && value === 0 ? "Prizemlje" : key in detailOptions ? (detailOptions[key as keyof typeof detailOptions] as Record<string, string>)[String(value)] : String(value);
    return [[detailLabels[key], label]];
  });
}
