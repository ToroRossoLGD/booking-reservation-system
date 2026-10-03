export const reportCategories = { misleading: "Netačni podaci", fraud: "Sumnja na prevaru", inappropriate: "Neprimeren sadržaj", duplicate: "Duplirani oglas", other: "Drugo" };
export const moderationLabels = { clear: "Objavljivanje dozvoljeno", suspended: "Suspendovan", appealed: "Čeka ponovni pregled", pending: "Čeka pregled", dismissed: "Prijava zatvorena bez uklanjanja", action_taken: "Oglas uklonjen iz javne ponude", hide: "Suspenzija", dismiss: "Prijava odbijena", appeal: "Zahtev vlasnika za pregled", restore: "Zabrana ukinuta", uphold: "Suspenzija potvrđena" };
export type ModerationCase = { id: number; title: string; state: "clear" | "suspended" | "appealed"; version: number; note: string; appeal: string; is_published: boolean };
export type ReportSnapshot = { title: string; description: string; city: string; offer_type: string; price_cents: number; currency: string };
export type PropertyReport = { snapshot: ReportSnapshot; id: number; property_id: number; category: keyof typeof reportCategories; details: string; status: "pending" | "dismissed" | "action_taken"; created_at: string; resolved_at: string | null; listing: ModerationCase };
export type ModerationEvent = { id: number; action: "hide" | "dismiss" | "appeal" | "restore" | "uphold"; note: string; version: number; created_at: string };
export type ModerationAction = { request_id: string; version: number; action: ModerationEvent["action"]; note: string };
export type ModerationPageData<T> = { items: T[]; total: number; has_next: boolean };
