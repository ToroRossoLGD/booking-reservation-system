export type AnalyticsMonth = { month: number; views: number; reservations: number; cancelled: number; nights: number; booked_value_cents: Record<string, number> };
export type PropertyAnalytics = { year: number; properties: { id: number; title: string; offer_type: string }[]; months: AnalyticsMonth[] };
