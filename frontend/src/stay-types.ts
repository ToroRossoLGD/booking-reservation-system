export type StayDates = { check_in: string; check_out: string; guests: number };

export function parseStayDates(params: URLSearchParams): StayDates | undefined {
  const check_in = params.get("check_in") ?? "";
  const check_out = params.get("check_out") ?? "";
  const guests = Number(params.get("guests"));
  const validDate = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
  if (!validDate(check_in) || !validDate(check_out) || !Number.isInteger(guests) || guests < 1 || guests > 100) return;
  const nights = (Date.parse(check_out) - Date.parse(check_in)) / 86400000;
  if (nights < 1 || nights > 90) return;
  return { check_in, check_out, guests };
}
export type StayQuote = { nights: number; nightly_rate_cents: number; total_cents: number; currency: string; timezone: string; payment_method: "pay_on_arrival" };
export type Stay = StayDates & { id: number; property_id: number; status: "confirmed" | "cancelled"; title: string; city: string; timezone: string; contact_email: string; guest_email?: string | null; nightly_rate_cents: number; total_cents: number; currency: string; created_at: string; payment_method: "pay_on_arrival" };
export type StayPage = { items: Stay[]; total: number; has_next: boolean };
export type StayCalendar = { start: string; end: string; occupied: { check_in: string; check_out: string }[] };
export type StayCreate = StayDates & { request_id: string; expected_total_cents: number; expected_currency: string };

export function stayMoney(cents: number, currency: string) {
  return new Intl.NumberFormat("sr-Latn", { style: "currency", currency }).format(cents / 100);
}
export function propertyToday(timezone = "Europe/Belgrade") {
  const parts = new Intl.DateTimeFormat("en", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  return ["year", "month", "day"].map(type => parts.find(part => part.type === type)?.value).join("-");
}
export function shiftDate(value: string, days: number) {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}
export function displayDate(value: string) {
  return new Intl.DateTimeFormat("sr-Latn", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${value}T12:00:00Z`));
}

export type StayBlock = { id: number; venue_id: number; check_in: string; check_out: string; reason: string; active: boolean; created_at: string };
export type StayBlockPage = { items: StayBlock[]; total: number; has_next: boolean };
export type StayBlockCreate = { check_in: string; check_out: string; reason: string; request_id: string };
