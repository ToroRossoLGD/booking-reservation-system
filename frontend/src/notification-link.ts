import { parseStayDates } from "./stay-types";

const known: Record<string, string> = {
  "/sales": "Moji upiti za kupovinu", "/owner/sales": "Upiti za prodaju nekretnina",
  "/moderation": "Prijave i moderacija",
  "/stays": "Moji boravci", "/owner/stays": "Rezervacije tvojih stanova",
  "/rentals": "Moji upiti za najam", "/owner/rentals": "Upiti za tvoje stanove",
};
export function notificationLinkLabel(path: string | null | undefined): string | null {
  if (!path) return null;
  if (Object.hasOwn(known, path)) return known[path];
  const match = path.match(/^\/properties\/([1-9]\d*)(\?[^#]*)?$/);
  if (!match || !Number.isSafeInteger(Number(match[1]))) return null;
  if (match[2]) {
    const params = new URLSearchParams(match[2]);
    if (Array.from(params.keys()).some(key => !["check_in", "check_out", "guests"].includes(key)) || params.size !== 3 || !parseStayDates(params)) return null;
  }
  return "Pogledaj oglas";
}
