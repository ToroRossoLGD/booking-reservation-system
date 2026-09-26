import type { Stay } from "./stay-types";
import type { RentalInquiry } from "./rental-types";

export type CalendarDownload = { filename: string; contents: string };

// RFC 5545 TEXT escaping and UTF-8 line folding (75 octets, including continuation).
function text(value: string) {
  const escaped = value.replace(/\\/g, "\\\\").replace(/\r\n|\r|\n/g, "\\n").replace(/;/g, "\\;").replace(/,/g, "\\,");
  return [...escaped].filter(character => character === "\t" || (character.charCodeAt(0) >= 32 && character.charCodeAt(0) !== 127)).join("");
}
function fold(line: string) {
  const encoder = new TextEncoder();
  let result = ""; let size = 0;
  for (const character of line) {
    const bytes = encoder.encode(character).length;
    if (size + bytes > 75) { result += "\r\n "; size = 1; }
    result += character; size += bytes;
  }
  return result;
}
function timestamp(value: string | Date) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) throw new Error("Invalid calendar date");
  return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}
function day(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value) throw new Error("Invalid calendar date");
  return value.replace(/-/g, "");
}
function calendar(uid: string, properties: string[], now: Date) {
  return ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Bookica//Property Calendar//SR", "CALSCALE:GREGORIAN", "BEGIN:VEVENT", `UID:${text(uid)}`, `DTSTAMP:${timestamp(now)}`, "CLASS:PRIVATE", "STATUS:CONFIRMED", ...properties, "END:VEVENT", "END:VCALENDAR"].map(fold).join("\r\n") + "\r\n";
}

export function stayCalendar(stay: Stay, origin: string, owner = false, now = new Date()): CalendarDownload | null {
  if (stay.status !== "confirmed") return null;
  const host = new URL(origin).host;
  const start = day(stay.check_in); const end = day(stay.check_out);
  if (end <= start) throw new Error("Invalid stay dates");
  const times = stay.check_in_time && stay.check_out_time ? `Prijava od ${stay.check_in_time}. Odjava do ${stay.check_out_time} (${stay.timezone}).` : "Tačno vreme dogovori sa domaćinom.";
  return { filename: `bookica-boravak-${stay.id}.ics`, contents: calendar(`stay-${stay.id}@${host}`, [
    `DTSTART;VALUE=DATE:${start}`, `DTEND;VALUE=DATE:${end}`,
    `SUMMARY:${text(`Boravak: ${stay.title}`)}`, `LOCATION:${text(stay.city)}`,
    `DESCRIPTION:${text(`Bookica boravak #${stay.id}. Dolazak: ${stay.check_in}. Odlazak: ${stay.check_out}. ${times} Ovo je kopija termina; izmene i otkazivanje proveri u Bookici.`)}`,
    `URL:${new URL(owner ? "/owner/stays" : "/stays", origin).href}`,
  ], now) };
}

export function viewingCalendar(inquiry: RentalInquiry, origin: string, owner = false, now = new Date()): CalendarDownload | null {
  if (inquiry.status !== "viewing_confirmed" || !inquiry.viewing_at) return null;
  // The API stores an instant. UTC avoids floating-time and DST ambiguity.
  if (!/(Z|[+-]\d{2}:\d{2})$/i.test(inquiry.viewing_at)) throw new Error("Viewing must include a timezone");
  return { filename: `bookica-razgledanje-${inquiry.id}.ics`, contents: calendar(`viewing-${inquiry.id}@${new URL(origin).host}`, [
    `DTSTART:${timestamp(inquiry.viewing_at)}`, `SEQUENCE:${inquiry.version}`,
    `SUMMARY:${text(`Razgledanje: ${inquiry.title}`)}`,
    `DESCRIPTION:${text(`Bookica upit #${inquiry.id}. Mesto sastanka i trajanje proveri u razgovoru. Ovo je kopija termina; izmene proveri u Bookici.`)}`,
    `URL:${new URL(owner ? "/owner/rentals" : "/rentals", origin).href}`,
  ], now) };
}
