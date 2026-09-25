import { expect, it } from "vitest";
import { stayCalendar, viewingCalendar } from "./calendar-export";
import type { Stay } from "./stay-types";
import type { RentalInquiry } from "./rental-types";

const origin = "https://bookica.example";
const now = new Date("2030-09-01T10:20:30Z");
const stay: Stay = { id: 7, property_id: 3, status: "confirmed", title: "Stan pored reke", city: "Novi Sad", contact_email: "private@example.com", guest_email: "guest@example.com", timezone: "Europe/Belgrade", check_in: "2030-10-04", check_out: "2030-10-07", guests: 2, nightly_rate_cents: 6500, total_cents: 19500, currency: "EUR", payment_method: "pay_on_arrival", created_at: "2030-09-01T00:00:00Z" };
const inquiry: RentalInquiry = { id: 9, property_id: 3, title: "Stan za najam", monthly_price_cents: 60000, currency: "EUR", move_in: "2030-10-01", duration_months: 12, message: "Private tenant message", owner_reply: "Private reply", viewing_at: "2030-09-25T14:00:00+02:00", status: "viewing_confirmed", version: 3, created_at: "2030-09-01T00:00:00Z" };
const unfold = (value: string) => value.replace(/\r\n /g, "");

it("exports all-day stay dates with exclusive checkout and required calendar fields", () => {
  const file = stayCalendar(stay, origin, false, now)!;
  expect(file.filename).toBe("bookica-boravak-7.ics");
  expect(file.contents).toContain("DTSTART;VALUE=DATE:20301004\r\nDTEND;VALUE=DATE:20301007");
  expect(file.contents).toContain("UID:stay-7@bookica.example\r\nDTSTAMP:20300901T102030Z");
  expect(file.contents).toContain("CLASS:PRIVATE");
  expect(file.contents.endsWith("END:VEVENT\r\nEND:VCALENDAR\r\n")).toBe(true);
  expect(file.contents).not.toContain("private@example.com");
  expect(file.contents).not.toContain("guest@example.com");
  expect(file.contents).not.toContain("ATTENDEE");
  expect(unfold(file.contents)).toContain(`URL:${origin}/stays`);
  expect(unfold(stayCalendar(stay, origin, true, now)!.contents)).toContain(`URL:${origin}/owner/stays`);
});

it("exports viewing instants in UTC without inventing an end time or exposing messages", () => {
  const file = viewingCalendar(inquiry, origin, false, now)!;
  expect(file.contents).toContain("DTSTART:20300925T120000Z");
  expect(file.contents).toContain("SEQUENCE:3");
  expect(file.contents).not.toContain("DTEND");
  expect(file.contents).not.toContain("DURATION");
  expect(file.contents).not.toContain("Private tenant message");
  expect(file.contents).not.toContain("Private reply");
  expect(unfold(file.contents)).toContain(`URL:${origin}/rentals`);
  expect(unfold(viewingCalendar(inquiry, origin, true, now)!.contents)).toContain(`URL:${origin}/owner/rentals`);
  expect(viewingCalendar({ ...inquiry, viewing_at: "2030-09-25T12:00:00Z" }, origin, false, now)!.contents).toBe(file.contents);
});

it("keeps event identity stable across re-exports and separates stays from viewings", () => {
  const first = stayCalendar(stay, origin, false, now)!.contents;
  const second = stayCalendar(stay, origin, true, new Date("2030-09-02T00:00:00Z"))!.contents;
  expect(first.match(/UID:([^\r]+)/)?.[1]).toBe(second.match(/UID:([^\r]+)/)?.[1]);
  expect(viewingCalendar({ ...inquiry, id: 7 }, origin)!.contents).toContain("UID:viewing-7@");
});

it("escapes user text and folds UTF-8 at 75 octets without splitting characters", () => {
  const title = "Čačak 🏠 ".repeat(20) + "\\,;\r\nBEGIN:VEVENT";
  const file = stayCalendar({ ...stay, title }, origin, false, now)!.contents;
  for (const line of file.split("\r\n")) expect(new TextEncoder().encode(line).length).toBeLessThanOrEqual(75);
  expect(file.split("\r\n").filter(line => line === "BEGIN:VEVENT")).toHaveLength(1);
  expect(unfold(file)).toContain("\\\\\\,\\;\\nBEGIN:VEVENT");
  expect(unfold(file)).toContain("Čačak 🏠 ".repeat(20));
});

it.each(["open", "viewing_proposed", "withdrawn", "closed"] as const)("does not export %s inquiries", status => {
  expect(viewingCalendar({ ...inquiry, status }, origin)).toBeNull();
});

it("rejects cancelled stays, missing viewing times and malformed dates", () => {
  expect(stayCalendar({ ...stay, status: "cancelled" }, origin)).toBeNull();
  expect(viewingCalendar({ ...inquiry, viewing_at: null }, origin)).toBeNull();
  expect(() => stayCalendar({ ...stay, check_out: stay.check_in }, origin)).toThrow();
  expect(() => stayCalendar({ ...stay, check_in: "2030-02-30" }, origin)).toThrow();
  expect(() => viewingCalendar({ ...inquiry, viewing_at: "2030-09-25T14:00:00" }, origin)).toThrow();
});
