import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import StayBooking from "./StayBooking";
import type { PropertyListing } from "./property-types";
import { propertyToday, shiftDate } from "./stay-types";

vi.mock("./api", () => ({ api: { stayCalendar: vi.fn(), stayQuote: vi.fn(), createStay: vi.fn() }, ApiError: class extends Error { constructor(message: string, public status: number) { super(message); } } }));
const property: PropertyListing = { id: 1, venue_id: 1, title: "Stan", city: "Beograd", description: "Udoban stan blizu centra grada.", offer_type: "short_stay", price_cents: 6500, currency: "EUR", rooms: 2, area_sqm: 50, is_published: true, contact_email: "host@example.com", booking_enabled: true, max_guests: 3, minimum_nights: 2, timezone: "Europe/Belgrade" };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.stayCalendar).mockResolvedValue({ start: "2026-10-01", end: "2026-11-01", occupied: [] });
  vi.mocked(api.stayQuote).mockResolvedValue({ nights: 2, nightly_rate_cents: 6500, total_cents: 13000, currency: "EUR", timezone: "Europe/Belgrade", check_in_time: "15:00", check_out_time: "10:30", payment_method: "pay_on_arrival" });
});

it("limits departure by owner rules and updates the limit when arrival changes", async () => {
  const user = userEvent.setup();
  render(<StayBooking property={{ ...property, maximum_nights: 3 }} />);
  const today = propertyToday("Europe/Belgrade");
  const arrival = shiftDate(today, 1);
  const departure = screen.getByLabelText("Odlazak");
  expect(screen.getByText(/Najviše 3 noćenja/)).toBeVisible();
  expect(departure).toHaveAttribute("max", shiftDate(arrival, 3));
  fireEvent.change(departure, { target: { value: shiftDate(arrival, 4) } });
  await user.click(screen.getByRole("button", { name: "Proveri dostupnost i cenu" }));
  expect(api.stayQuote).not.toHaveBeenCalled();
  fireEvent.change(departure, { target: { value: shiftDate(arrival, 3) } });
  await user.click(screen.getByRole("button", { name: "Proveri dostupnost i cenu" }));
  expect(api.stayQuote).toHaveBeenCalledWith(property.id, { check_in: arrival, check_out: shiftDate(arrival, 3), guests: 1 });
  await screen.findByRole("button", { name: "Potvrdi rezervaciju" });
  fireEvent.change(screen.getByLabelText("Dolazak"), { target: { value: shiftDate(today, 364) } });
  expect(departure).toHaveAttribute("max", shiftDate(today, 365));
  expect(screen.queryByRole("button", { name: "Potvrdi rezervaciju" })).not.toBeInTheDocument();
});

it("uses the server quote, retries with the same request ID, and invalidates a quote when guests change", async () => {
  const user = userEvent.setup(); render(<StayBooking property={property} />);
  await user.click(screen.getByRole("button", { name: "Proveri dostupnost i cenu" }));
  await screen.findByRole("button", { name: "Potvrdi rezervaciju" });
  expect(screen.getByText(/Prijava od 15:00 · Odjava do 10:30/)).toBeVisible();
  await user.clear(screen.getByLabelText("Broj gostiju"));
  await user.type(screen.getByLabelText("Broj gostiju"), "2");
  expect(screen.queryByRole("button", { name: "Potvrdi rezervaciju" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Proveri dostupnost i cenu" }));
  vi.mocked(api.createStay).mockRejectedValueOnce(new Error("network"));
  await user.click(await screen.findByRole("button", { name: "Potvrdi rezervaciju" }));
  await screen.findByRole("alert");
  const request = vi.mocked(api.createStay).mock.calls[0][1];
  expect(request).toMatchObject({ guests: 2, expected_total_cents: 13000, expected_currency: "EUR", expected_check_in_time: "15:00", expected_check_out_time: "10:30", expected_timezone: "Europe/Belgrade" });
  vi.mocked(api.createStay).mockResolvedValue({ ...request, id: 8, status: "confirmed", total_cents: 13000, currency: "EUR", property_id: 1, title: property.title, city: property.city, timezone: "Europe/Belgrade", contact_email: property.contact_email, nightly_rate_cents: 6500, created_at: new Date().toISOString(), payment_method: "pay_on_arrival" });
  await user.click(screen.getByRole("button", { name: "Potvrdi rezervaciju" }));
  await waitFor(() => expect(api.createStay).toHaveBeenLastCalledWith(1, request));
  expect(await screen.findByText(/Rezervacija je potvrđena/)).toBeVisible();
});

it("shows conflicts and requires a new quote instead of keeping stale confirmation", async () => {
  const user = userEvent.setup(); render(<StayBooking property={property} />);
  await user.click(screen.getByRole("button", { name: "Proveri dostupnost i cenu" }));
  vi.mocked(api.createStay).mockRejectedValue(new ApiError("Occupied", 409));
  await user.click(await screen.findByRole("button", { name: "Potvrdi rezervaciju" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Dostupnost ili uslovi su se promenili");
  expect(screen.queryByRole("button", { name: "Potvrdi rezervaciju" })).not.toBeInTheDocument();
});
