import type {
  AvailableResource,
  AvailableSlot,
  AvailabilityException,
  AvailabilityRule,
  AddOn,
  CheckoutSession,
  Favorite,
  MediaAsset,
  Notification,
  OwnerReservation,
  OwnerResource,
  OwnerStats,
  OwnerVenue,
  PageResult,
  Promotion,
  Quote,
  RatingSummary,
  Reservation,
  ReservationWorkspace,
  Resource,
  User,
  Venue,
} from "./types";

import type { PropertyInput, PropertyListing, PropertyPage, PropertyPhoto, PropertySearchFilters } from "./property-types";
import type { RentalInquiry, RentalInquiryInput, RentalInquiryPage, RentalUpdate, RentalMessage, RentalMessagePage } from "./rental-types";
import type { Stay, StayCalendar, StayCreate, StayDates, StayPage, StayQuote } from "./stay-types";

const API_URL = import.meta.env.VITE_API_URL ?? "/api";

export const googleLoginUrl = `${API_URL}/auth/google/login`;

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("bookica_token");
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (
    options.body &&
    !(options.body instanceof URLSearchParams) &&
    !(options.body instanceof FormData)
  )
    headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(
      payload?.detail ?? "Something went wrong",
      response.status,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const api = {
  property: (id: number, signal?: AbortSignal) => request<PropertyListing>(`/properties/${id}`, { signal }),
  propertyPhotoUrl: (propertyId: number, photoId: number, thumbnail = false) => `${API_URL}/properties/${propertyId}/photos/${photoId}/image?thumbnail=${thumbnail}`,
  ownerPhotos: (id: number) => request<PropertyPhoto[]>(`/owner/properties/${id}/photos`),
  uploadPropertyPhoto: (id: number, file: File, requestId: string) => { const body = new FormData(); body.append("file", file); body.append("request_id", requestId); return request<PropertyPhoto>(`/owner/properties/${id}/photos`, { method: "POST", body }); },
  reorderPropertyPhotos: (id: number, photoIds: number[]) => request<PropertyPhoto[]>(`/owner/properties/${id}/photos/order`, { method: "PUT", body: JSON.stringify({ photo_ids: photoIds }) }),
  deletePropertyPhoto: (id: number, photoId: number) => request<void>(`/owner/properties/${id}/photos/${photoId}`, { method: "DELETE" }),
  ownerPhotoBlob: async (id: number, photoId: number, signal: AbortSignal) => {
    const response = await fetch(`${API_URL}/owner/properties/${id}/photos/${photoId}/image?thumbnail=true`, { signal, headers: { Authorization: `Bearer ${localStorage.getItem("bookica_token") ?? ""}` } });
    if (!response.ok) throw new ApiError("Photo unavailable", response.status);
    return response.blob();
  },
  savedProperties: (offset = 0, signal?: AbortSignal) => request<PropertyPage>(`/favorites/properties?offset=${offset}&limit=12`, { signal }),
  savedPropertyIds: (ids: number[], signal?: AbortSignal) => request<{ property_ids: number[] }>(`/favorites/properties/status?${ids.map(id => `property_ids=${id}`).join("&")}`, { signal }),
  saveProperty: (id: number) => request<{ property_id: number; saved: true }>(`/favorites/properties/${id}`, { method: "PUT" }),
  unsaveProperty: (id: number) => request<void>(`/favorites/properties/${id}`, { method: "DELETE" }),
  rentalMessages: (id: number, beforeId?: number) => request<RentalMessagePage>(`/rental-inquiries/${id}/messages${beforeId ? `?before_id=${beforeId}` : ""}`),
  sendRentalMessage: (id: number, body: string, requestId: string) => request<RentalMessage>(`/rental-inquiries/${id}/messages`, { method: "POST", body: JSON.stringify({ body, request_id: requestId }) }),
  readRentalMessages: (id: number, messageIds: number[]) => request<{ unread_count: number }>(`/rental-inquiries/${id}/messages/read`, { method: "POST", body: JSON.stringify({ message_ids: messageIds }) }),
  createRentalInquiry: (id: number, data: RentalInquiryInput) => request<RentalInquiry>(`/properties/${id}/rental-inquiries`, { method: "POST", body: JSON.stringify(data) }),
  rentalInquiries: (owner = false, offset = 0) => request<RentalInquiryPage>(`${owner ? "/owner/rental-inquiries" : "/rental-inquiries/mine"}?offset=${offset}&limit=20`),
  updateRentalInquiry: (id: number, data: RentalUpdate) => request<RentalInquiry>(`/rental-inquiries/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  stayQuote: (id: number, dates: StayDates) => request<StayQuote>(`/properties/${id}/stay-quote`, { method: "POST", body: JSON.stringify(dates) }),
  createStay: (id: number, data: StayCreate) => request<Stay>(`/properties/${id}/stays`, { method: "POST", body: JSON.stringify(data) }),
  stayCalendar: (id: number, start: string, end: string, signal?: AbortSignal) => request<StayCalendar>(`/properties/${id}/calendar?${new URLSearchParams({ start, end })}`, { signal }),
  myStays: (owner = false, offset = 0) => request<StayPage>(`${owner ? "/owner/stays" : "/stays/mine"}?offset=${offset}&limit=20`),
  cancelStay: (id: number) => request<Stay>(`/stays/${id}/cancel`, { method: "POST" }),
  properties: (city: string, offerType: string, offset = 0, signal?: AbortSignal, filters: PropertySearchFilters = {}) => {
    const params = new URLSearchParams({ city, offset: String(offset), limit: "12" });
    if (offerType) params.set("offer_type", offerType);
    Object.entries(filters).forEach(([key, value]) => { if (value !== undefined) params.set(key, String(value)); });
    return request<PropertyPage>(`/properties?${params}`, { signal });
  },
  ownerProperties: (offset = 0) => request<PropertyPage>(`/owner/properties?offset=${offset}&limit=20`),
  createProperty: (data: PropertyInput) => request<PropertyListing>("/properties", { method: "POST", body: JSON.stringify(data) }),
  updateProperty: (id: number, data: PropertyInput) => request<PropertyListing>(`/properties/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  venues: () => request<Venue[]>("/venues"),
  resources: (venueId: number) =>
    request<Resource[]>(`/venues/${venueId}/resources`),
  ratingSummary: (resourceId: number) =>
    request<RatingSummary>(`/resources/${resourceId}/rating-summary`),
  availableSlots: (resourceId: number, date: string) =>
    request<AvailableSlot[]>(
      `/resources/${resourceId}/available-slots?date=${encodeURIComponent(date)}&slot_minutes=60`,
    ),
  searchAvailable: (
    startTime: string,
    endTime: string,
    guests: number,
    resourceType: string,
    q: string,
  ) => {
    const params = new URLSearchParams({
      start_time: startTime,
      end_time: endTime,
      minimum_capacity: String(guests),
      limit: "50",
    });
    if (resourceType) params.set("resource_type", resourceType);
    if (q) params.set("q", q);
    return request<
      PageResult<AvailableResource> & { start_time: string; end_time: string }
    >(`/resources/search/available?${params}`);
  },
  activePromotions: () => request<Promotion[]>("/promotions/active"),
  login: async (email: string, password: string) => {
    const body = new URLSearchParams({ username: email, password });
    const result = await request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body,
    });
    localStorage.setItem("bookica_token", result.access_token);
    return result;
  },
  register: (email: string, password: string) =>
    request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, role: "customer" }),
    }),
  me: () => request<User>("/auth/me"),
  quote: (
    resourceId: number,
    startTime: string,
    endTime: string,
    partySize: number,
    promotionCode?: string,
  ) =>
    request<Quote>("/reservations/quote", {
      method: "POST",
      body: JSON.stringify({
        resource_id: resourceId,
        start_time: startTime,
        end_time: endTime,
        party_size: partySize,
        promotion_code: promotionCode || null,
      }),
    }),
  reserve: (
    resourceId: number,
    startTime: string,
    endTime: string,
    partySize: number,
    promotionCode?: string,
  ) =>
    request("/reservations", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({
        resource_id: resourceId,
        start_time: startTime,
        end_time: endTime,
        party_size: partySize,
        promotion_code: promotionCode || null,
      }),
    }),
  myReservations: (status = "") =>
    request<PageResult<Reservation>>(
      `/reservations/my?limit=50${status ? `&status=${encodeURIComponent(status)}` : ""}`,
    ),
  cancelReservation: (reservationId: number) =>
    request(`/reservations/${reservationId}/cancel`, { method: "PATCH" }),
  reservationWorkspace: (reservationId: number) =>
    request<ReservationWorkspace>(`/reservations/${reservationId}/workspace`),
  rescheduleReservation: (
    reservationId: number,
    startTime: string,
    endTime: string,
  ) =>
    request<Reservation>(`/reservations/${reservationId}/reschedule`, {
      method: "PATCH",
      body: JSON.stringify({ start_time: startTime, end_time: endTime }),
    }),
  createCheckout: (reservationId: number) =>
    request<CheckoutSession>(
      `/payments/reservations/${reservationId}/checkout`,
      { method: "POST" },
    ),
  favorites: () => request<Favorite[]>("/favorites/resources"),
  addFavorite: (resourceId: number) =>
    request(`/favorites/resources/${resourceId}`, { method: "POST" }),
  removeFavorite: (resourceId: number) =>
    request(`/favorites/resources/${resourceId}`, { method: "DELETE" }),
  notifications: () =>
    request<PageResult<Notification>>("/notifications/my?limit=50"),
  markNotificationRead: (notificationId: number) =>
    request<Notification>(`/notifications/${notificationId}/read`, {
      method: "PATCH",
    }),
  markAllNotificationsRead: () =>
    request<void>("/notifications/read-all", { method: "POST" }),
  dismissNotification: (notificationId: number) =>
    request<void>(`/notifications/${notificationId}`, { method: "DELETE" }),
  dismissReadNotifications: () =>
    request<{ dismissed_count: number }>("/notifications/read", {
      method: "DELETE",
    }),
  ownerVenues: () => request<OwnerVenue[]>("/owner/venues"),
  ownerResources: () => request<OwnerResource[]>("/owner/resources"),
  ownerReservations: () => request<OwnerReservation[]>("/owner/reservations"),
  ownerStats: () => request<OwnerStats>("/owner/stats"),
  venue: (venueId: number) => request<Venue>(`/venues/${venueId}`),
  updateVenue: (venueId: number, data: Partial<Venue>) =>
    request<Venue>(`/venues/${venueId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  updateBookingRules: (venueId: number, data: {
    minimum_booking_notice_minutes: number;
    maximum_advance_booking_days: number;
    minimum_booking_duration_minutes: number;
    maximum_booking_duration_minutes: number;
    max_active_reservations_per_customer: number;
  }) => request(`/venues/${venueId}/booking-rules`, { method: "PATCH", body: JSON.stringify(data) }),
  updateCancellationPolicy: (venueId: number, data: {
    free_cancellation_hours: number;
    late_cancellation_refund_percent: number;
  }) => request(`/venues/${venueId}/cancellation-policy`, { method: "PATCH", body: JSON.stringify(data) }),
  availabilityRules: (resourceId: number) => request<AvailabilityRule[]>(`/resources/${resourceId}/availability-rules`),
  createAvailabilityRule: (resourceId: number, data: { weekday: number; start_time: string; end_time: string }) => request<AvailabilityRule>(`/resources/${resourceId}/availability-rules`, { method: "POST", body: JSON.stringify(data) }),
  deleteAvailabilityRule: (resourceId: number, ruleId: number) => request(`/resources/${resourceId}/availability-rules/${ruleId}`, { method: "DELETE" }),
  availabilityExceptions: (resourceId: number) => request<AvailabilityException[]>(`/resources/${resourceId}/availability-exceptions`),
  createAvailabilityException: (resourceId: number, data: { start_time: string; end_time: string; reason?: string }) => request<AvailabilityException>(`/resources/${resourceId}/availability-exceptions`, { method: "POST", body: JSON.stringify(data) }),
  deleteAvailabilityException: (resourceId: number, exceptionId: number) => request(`/resources/${resourceId}/availability-exceptions/${exceptionId}`, { method: "DELETE" }),
  venuePromotions: (venueId: number) => request<Promotion[]>(`/venues/${venueId}/promotions`),
  createPromotion: (venueId: number, data: { code: string; discount_percent: number; valid_from: string; valid_until: string; max_redemptions: number | null }) => request<Promotion>(`/venues/${venueId}/promotions`, { method: "POST", body: JSON.stringify(data) }),
  deactivatePromotion: (promotionId: number) => request<Promotion>(`/promotions/${promotionId}/deactivate`, { method: "PATCH" }),
  managedAddOns: (venueId: number) => request<AddOn[]>(`/venues/${venueId}/add-ons/manage`),
  createAddOn: (venueId: number, data: { name: string; description?: string; price_cents: number; stock: number }) => request<AddOn>(`/venues/${venueId}/add-ons`, { method: "POST", body: JSON.stringify(data) }),
  updateAddOn: (addOnId: number, data: Partial<AddOn>) => request<AddOn>(`/add-ons/${addOnId}`, { method: "PATCH", body: JSON.stringify(data) }),
  createVenue: (data: {
    name: string;
    address: string;
    description?: string;
    latitude?: number;
    longitude?: number;
  }) =>
    request<Venue>("/venues", { method: "POST", body: JSON.stringify(data) }),
  createResource: (
    venueId: number,
    data: {
      name: string;
      resource_type: string;
      capacity: number;
      hourly_rate_cents: number;
      currency: string;
    },
  ) =>
    request<Resource>(`/venues/${venueId}/resources`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  venueMedia: (venueId: number) =>
    request<MediaAsset[]>(`/venues/${venueId}/media`),
  resourceMedia: (resourceId: number) =>
    request<MediaAsset[]>(`/resources/${resourceId}/media`),
  uploadVenueMedia: (venueId: number, file: File) => {
    const body = new FormData();
    body.set("file", file);
    return request<MediaAsset>(`/venues/${venueId}/media`, {
      method: "POST",
      body,
    });
  },
  uploadResourceMedia: (resourceId: number, file: File) => {
    const body = new FormData();
    body.set("file", file);
    return request<MediaAsset>(`/resources/${resourceId}/media`, {
      method: "POST",
      body,
    });
  },
};
