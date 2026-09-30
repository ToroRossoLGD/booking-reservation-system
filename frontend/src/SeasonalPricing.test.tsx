import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api } from "./api";
import PropertyManager from "./PropertyManager";
import PropertyCard from "./PropertyCard";
import StayBooking from "./StayBooking";
import type { PropertyListing } from "./property-types";
import { propertyToday, shiftDate } from "./stay-types";

vi.mock("./api", () => ({ api: { ownerProperties: vi.fn(), updateProperty: vi.fn(), stayCalendar: vi.fn(), stayQuote: vi.fn(), createStay: vi.fn() }, ApiError: class extends Error {} }));
const today = propertyToday();
const start = shiftDate(today, 3);
const end = shiftDate(today, 5);
const listing: PropertyListing = { id: 7, venue_id: 1, title: "Stan sa sezonskom cenom", description: "Udoban stan u centru grada sa terasom.", city: "Beograd", offer_type: "short_stay", area_sqm: 60, rooms: 2, price_cents: 6500, currency: "EUR", contact_email: "owner@example.com", is_published: true, booking_enabled: true, seasonal_rates: [{ start, end, price_cents: 10000, label: "Sezona" }] };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.ownerProperties).mockResolvedValue({ items: [listing], total: 1, offset: 0, limit: 20, has_next: false });
  vi.mocked(api.updateProperty).mockResolvedValue(listing);
  vi.mocked(api.stayCalendar).mockResolvedValue({ start, end, occupied: [] });
});
function manager() { return render(<PropertyManager venues={[{ id: 1, name: "Stan", description: null, address: "Centar", owner_id: 1 }]} />); }

it("rejects overlapping owner periods then saves adjacent periods in cents", async () => {
  const user = userEvent.setup(); manager();
  await user.click(await screen.findByRole("button", { name: `Izmeni: ${listing.title}` }));
  expect(screen.getByLabelText("Sezonska cena po noći")).toHaveValue(100);
  await user.click(screen.getByRole("button", { name: "Dodaj sezonski period" }));
  fireEvent.change(screen.getAllByLabelText("Prva noć")[1], { target: { value: start } });
  fireEvent.change(screen.getAllByLabelText("Do datuma (nije uključen)")[1], { target: { value: shiftDate(end, 2) } });
  await user.type(screen.getAllByLabelText("Sezonska cena po noći")[1], "85.25");
  await user.click(screen.getByRole("button", { name: "Sačuvaj oglas" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("ne smeju da se preklapaju");
  expect(api.updateProperty).not.toHaveBeenCalled();
  fireEvent.change(screen.getAllByLabelText("Prva noć")[1], { target: { value: end } });
  await user.click(screen.getByRole("button", { name: "Sačuvaj oglas" }));
  await waitFor(() => expect(api.updateProperty).toHaveBeenCalledWith(7, expect.objectContaining({ seasonal_rates: [...listing.seasonal_rates!, { start: end, end: shiftDate(end, 2), price_cents: 8525, label: "" }] })));
});

it("clears seasons when switching from nightly stays to sale", async () => {
  const user = userEvent.setup(); manager();
  await user.click(await screen.findByRole("button", { name: `Izmeni: ${listing.title}` }));
  await user.selectOptions(screen.getByLabelText("Vrsta ponude"), "sale");
  expect(screen.queryByRole("button", { name: "Dodaj sezonski period" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Sačuvaj oglas" }));
  await waitFor(() => expect(api.updateProperty).toHaveBeenCalledWith(7, expect.objectContaining({ offer_type: "sale", seasonal_rates: [] })));
});

it("confirms the server's itemized quote and retains its breakdown after booking", async () => {
  const prices = [{ date: start, price_cents: 10000 }, { date: shiftDate(start, 1), price_cents: 6500 }];
  vi.mocked(api.stayQuote).mockResolvedValue({ nights: 2, nightly_prices: prices, nightly_rate_cents: 6500, total_cents: 16500, currency: "EUR", timezone: "Europe/Belgrade", payment_method: "pay_on_arrival" });
  vi.mocked(api.createStay).mockResolvedValue({ ...listing, id: 42, property_id: 7, check_in: start, check_out: end, guests: 1, status: "confirmed", nightly_prices: prices, nightly_rate_cents: 6500, total_cents: 16500, created_at: new Date().toISOString(), timezone: "Europe/Belgrade", payment_method: "pay_on_arrival" });
  const user = userEvent.setup(); render(<StayBooking property={listing} initialDates={{ check_in: start, check_out: end, guests: 1 }} />);
  await user.click(screen.getByRole("button", { name: "Proveri dostupnost i cenu" }));
  await user.click(await screen.findByText("Obračun po noćima (2)"));
  expect(screen.getByRole("table")).toHaveTextContent("100,00");
  expect(screen.getByRole("table")).toHaveTextContent("65,00");
  await user.click(screen.getByRole("button", { name: "Potvrdi rezervaciju" }));
  await screen.findByText(/Rezervacija je potvrđena/);
  expect(api.createStay).toHaveBeenCalledWith(7, expect.objectContaining({ expected_total_cents: 16500, expected_nightly_prices: prices }));
  expect(screen.getByText("Obračun po noćima (2)")).toBeInTheDocument();
});

it("shows the date search total instead of multiplying the base rate", () => {
  render(<PropertyCard property={{ ...listing, stay_total_cents: 16500 }} stayDates={{ check_in: start, check_out: end, guests: 1 }} />);
  expect(screen.getByText(/165,00/)).toBeVisible();
  expect(screen.getByText(/boravak/)).toBeVisible();
  expect(screen.queryByText(/^65,00/)).not.toBeInTheDocument();
});
