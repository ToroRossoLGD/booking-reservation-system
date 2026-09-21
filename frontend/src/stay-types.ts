export type StayDates = { check_in: string; check_out: string; guests: number };
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
