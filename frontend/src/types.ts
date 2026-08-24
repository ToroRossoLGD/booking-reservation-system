export type User = { id: number; email: string; role: string };

export type Venue = {
  id: number; name: string; description: string | null; address: string;
  owner_id: number; free_cancellation_hours: number;
  late_cancellation_refund_percent: number; minimum_booking_notice_minutes: number;
  maximum_advance_booking_days: number; minimum_booking_duration_minutes: number;
  maximum_booking_duration_minutes: number; max_active_reservations_per_customer: number;
};

export type Resource = {
  id: number; name: string; resource_type: string; capacity: number;
  hourly_rate_cents: number; currency: string; venue_id: number;
};

export type Quote = { amount_cents: number; currency: string; duration_minutes: number };
