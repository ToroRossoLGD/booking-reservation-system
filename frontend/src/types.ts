export type User = { id: number; email: string; role: string };

export type Venue = {
  id: number;
  name: string;
  description: string | null;
  address: string;
  latitude: number | null;
  longitude: number | null;
  owner_id: number;
  free_cancellation_hours: number;
  late_cancellation_refund_percent: number;
  minimum_booking_notice_minutes: number;
  maximum_advance_booking_days: number;
  minimum_booking_duration_minutes: number;
  maximum_booking_duration_minutes: number;
  max_active_reservations_per_customer: number;
};

export type Resource = {
  id: number;
  name: string;
  resource_type: string;
  capacity: number;
  hourly_rate_cents: number;
  currency: string;
  venue_id: number;
};

export type Quote = {
  amount_cents: number;
  currency: string;
  duration_minutes: number;
};

export type RatingSummary = {
  resource_id: number;
  average_rating: number;
  review_count: number;
};

export type AvailableSlot = {
  start_time: string;
  end_time: string;
  available: boolean;
  remaining_capacity: number;
};

export type AvailableResource = Resource & {
  remaining_capacity: number;
  venue_name: string;
  venue_address: string;
};

export type PopularVenue = Venue & {
  average_rating: number | null;
  review_count: number;
  first_available_at: string | null;
};

export type Promotion = {
  id: number;
  code: string;
  venue_id: number;
  discount_percent: number;
  valid_from: string;
  valid_until: string;
  max_redemptions: number | null;
  redemption_count: number;
  is_active: boolean;
  created_at: string;
};

export type Reservation = {
  id: number;
  start_time: string;
  end_time: string;
  status: string;
  hold_expires_at: string | null;
  resource_id: number;
  party_size: number;
  quoted_amount_cents: number;
  quoted_currency: string;
  attendance_status: string;
};

export type PageResult<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  has_next: boolean;
};

export type Favorite = {
  favorite_id: number;
  resource_id: number;
  resource_name: string;
  resource_type: string;
  capacity: number;
  venue_id: number;
  venue_name: string;
  venue_address: string;
  created_at: string;
};

export type Notification = {
  id: number;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
};

export type OwnerVenue = {
  id: number;
  name: string;
  description: string | null;
  address: string;
  owner_id: number;
};
export type OwnerResource = {
  id: number;
  name: string;
  resource_type: string;
  capacity: number;
  venue_id: number;
  venue_name: string;
};
export type OwnerReservation = Reservation & {
  resource_name: string;
  venue_id: number;
  venue_name: string;
  user_id: number;
};
export type OwnerStats = {
  total_venues: number;
  total_resources: number;
  total_reservations: number;
  reservations_by_status: Record<string, number>;
  total_revenue_cents: number;
  top_resources: {
    resource_id: number;
    resource_name: string;
    reservation_count: number;
  }[];
};

export type MediaAsset = {
  id: number;
  venue_id: number | null;
  resource_id: number | null;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  caption: string | null;
  sort_order: number;
  created_at: string;
  url: string;
};

export type CheckoutSession = {
  payment_id: number;
  checkout_session_id: string;
  checkout_url: string;
  test_mode: boolean;
};

export type ReservationEvent = {
  id: number;
  event_type: string;
  actor_role: string;
  previous_status: string | null;
  new_status: string;
  details: Record<string, unknown>;
  occurred_at: string;
};

export type CancellationPreview = {
  refund_percentage: number;
  refund_amount_cents: number;
  cancellation_fee_cents: number;
  applied_free_cancellation_hours: number;
  applied_late_refund_percent: number;
};

export type ReservationWorkspace = {
  reservation: Reservation;
  resource: Pick<Resource, "id" | "name" | "resource_type" | "capacity">;
  venue: Pick<Venue, "id" | "name" | "address">;
  payment: {
    id: number;
    amount_cents: number;
    currency: string;
    status: string;
  } | null;
  timeline: ReservationEvent[];
  allowed_actions: string[];
  cancellation_preview: CancellationPreview | null;
};
