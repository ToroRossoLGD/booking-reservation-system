import type { OfferType, PropertySearchFilters } from "./property-types";
import { parseStayDates } from "./stay-types";

export type PropertySearchState = { city: string; offer: OfferType | ""; offset: number; filters: PropertySearchFilters };

export function readPropertySearch(search: string): PropertySearchState {
  const params = new URLSearchParams(search);
  const offer = params.get("offer_type") ?? "";
  const state: PropertySearchState = { city: (params.get("city") ?? "").trim().slice(0, 100), offer: ["short_stay", "long_term", "sale"].includes(offer) ? offer as OfferType : "", offset: 0, filters: {} };
  const number = (key: string, min: number, max: number) => {
    const raw = params.get(key);
    if (raw === null || !/^\d+$/.test(raw)) return undefined;
    const value = Number(raw);
    return Number.isSafeInteger(value) && value >= min && value <= max ? value : undefined;
  };
  const offset = number("offset", 0, 2147483647);
  state.offset = offset === undefined ? 0 : Math.floor(offset / 12) * 12;
  const { filters } = state;
  for (const [lower, upper, min, max] of [
    ["min_area_sqm", "max_area_sqm", 1, 100000],
    ["min_price_cents", "max_price_cents", 0, 1000000000000],
  ] as const) {
    const start = number(lower, min, max); const end = number(upper, min, max);
    if (start !== undefined && end !== undefined && start > end) continue;
    if (start !== undefined) filters[lower] = start;
    if (end !== undefined) filters[upper] = end;
  }
  const rooms = number("rooms", 0, 100);
  if (rooms !== undefined) filters.rooms = rooms;
  const sort = params.get("sort");
  if (sort && ["price_asc", "price_desc", "area_desc"].includes(sort)) filters.sort = sort as PropertySearchFilters["sort"];
  const currency = params.get("currency");
  if (currency && ["EUR", "RSD", "USD"].includes(currency)) filters.currency = currency as PropertySearchFilters["currency"];
  if (!state.offer || !filters.currency) {
    delete filters.min_price_cents; delete filters.max_price_cents;
    if (filters.sort?.startsWith("price_")) delete filters.sort;
  }
  const dates = parseStayDates(params);
  if (state.offer === "short_stay" && dates && !dates.check_in.startsWith("0000") && !dates.check_out.startsWith("0000")) Object.assign(filters, dates);
  return state;
}

export function propertySearchPath(state: PropertySearchState): string {
  const params = new URLSearchParams();
  if (state.city) params.set("city", state.city);
  if (state.offer) params.set("offer_type", state.offer);
  for (const key of ["currency", "min_price_cents", "max_price_cents", "min_area_sqm", "max_area_sqm", "rooms", "sort", "check_in", "check_out", "guests"] as const) {
    const value = state.filters[key];
    if (value !== undefined && value !== "newest") params.set(key, String(value));
  }
  if (state.offset) params.set("offset", String(state.offset));
  return params.size ? `/?${params}` : "/";
}
