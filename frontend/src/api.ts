import type { AvailableSlot, Promotion, Quote, RatingSummary, Resource, User, Venue } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("bookica_token");
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof URLSearchParams)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(payload?.detail ?? "Something went wrong", response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const api = {
  venues: () => request<Venue[]>("/venues"),
  resources: (venueId: number) => request<Resource[]>(`/venues/${venueId}/resources`),
  ratingSummary: (resourceId: number) => request<RatingSummary>(`/resources/${resourceId}/rating-summary`),
  availableSlots: (resourceId: number, date: string) => request<AvailableSlot[]>(`/resources/${resourceId}/available-slots?date=${encodeURIComponent(date)}&slot_minutes=60`),
  activePromotions: () => request<Promotion[]>("/promotions/active"),
  login: async (email: string, password: string) => {
    const body = new URLSearchParams({ username: email, password });
    const result = await request<{ access_token: string }>("/auth/login", { method: "POST", body });
    localStorage.setItem("bookica_token", result.access_token);
    return result;
  },
  register: (email: string, password: string) => request<User>("/auth/register", {
    method: "POST", body: JSON.stringify({ email, password, role: "customer" }),
  }),
  me: () => request<User>("/auth/me"),
  quote: (resourceId: number, startTime: string, endTime: string, partySize: number, promotionCode?: string) => request<Quote>("/reservations/quote", {
    method: "POST", body: JSON.stringify({ resource_id: resourceId, start_time: startTime, end_time: endTime, party_size: partySize, promotion_code: promotionCode || null }),
  }),
  reserve: (resourceId: number, startTime: string, endTime: string, partySize: number, promotionCode?: string) => request("/reservations", {
    method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({ resource_id: resourceId, start_time: startTime, end_time: endTime, party_size: partySize, promotion_code: promotionCode || null }),
  }),
};
