import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import PropertyManager from "./PropertyManager";
import { api } from "./api";

vi.mock("./api", () => ({ api: { ownerProperties: vi.fn(), createProperty: vi.fn(), updateProperty: vi.fn() }, ApiError: class extends Error {} }));

it("edits the nightly maximum and hides the control for other offers", async () => {
  vi.clearAllMocks();
  const listing = { id: 8, venue_id: 1, title: "Stan na dan", description: "Udoban stan u centru grada sa terasom.", city: "Beograd", offer_type: "short_stay" as const, area_sqm: 60, rooms: 2, price_cents: 8500, currency: "EUR" as const, contact_email: "owner@example.com", is_published: true, maximum_nights: 14 };
  vi.mocked(api.ownerProperties).mockResolvedValue({ items: [listing], total: 1, limit: 20, offset: 0, has_next: false });
  vi.mocked(api.updateProperty).mockResolvedValue({ ...listing, maximum_nights: 7 });
  const user = userEvent.setup();
  render(<PropertyManager venues={[{ id: 1, name: "Objekat", description: null, address: "Centar", owner_id: 1 }]} />);
  await user.click(await screen.findByRole("button", { name: "Izmeni: Stan na dan" }));
  const maximum = screen.getByLabelText(/Maksimalan broj noćenja/);
  expect(maximum).toHaveValue(14);
  await user.clear(screen.getByLabelText("Najava dolaska (dana unapred)"));
  await user.type(screen.getByLabelText("Najava dolaska (dana unapred)"), "3");
  await user.clear(screen.getByLabelText(/Pauza za pripremu/));
  await user.type(screen.getByLabelText(/Pauza za pripremu/), "2");
  await user.clear(maximum);
  await user.type(maximum, "7");
  await user.click(screen.getByRole("button", { name: "Sačuvaj oglas" }));
  await waitFor(() => expect(api.updateProperty).toHaveBeenCalledWith(8, expect.objectContaining({ maximum_nights: 7, advance_notice_days: 3, preparation_days: 2 })));
  await user.click(await screen.findByRole("button", { name: "Izmeni: Stan na dan" }));
  await user.selectOptions(screen.getByLabelText("Vrsta ponude"), "sale");
  expect(screen.queryByLabelText(/Maksimalan broj noćenja/)).not.toBeInTheDocument();
});

it("publishes a property with the selected price unit and can withdraw it", async () => {
  const listing = { id: 7, venue_id: 1, title: "Stan za najam", description: "Udoban stan u centru grada sa terasom.", city: "Beograd", offer_type: "long_term" as const, area_sqm: 60, rooms: 2, price_cents: 85000, currency: "EUR" as const, contact_email: "owner@example.com", is_published: true };
  const page = { items: [listing], total: 1, limit: 20, offset: 0, has_next: false };
  vi.mocked(api.ownerProperties).mockResolvedValueOnce({ ...page, items: [], total: 0 }).mockResolvedValue(page);
  vi.mocked(api.createProperty).mockResolvedValue(listing);
  vi.mocked(api.updateProperty).mockResolvedValue({ ...listing, is_published: false });
  const user = userEvent.setup();
  render(<PropertyManager venues={[{ id: 1, name: "Moj objekat", description: null, address: "Centar", owner_id: 1 }]} />);
  await screen.findByText(/Još nemaš oglase/);
  await user.click(screen.getByRole("button", { name: "Novi oglas" }));
  await user.selectOptions(screen.getByLabelText("Vrsta ponude"), "long_term");
  await user.type(screen.getByLabelText("Naslov oglasa"), listing.title);
  await user.type(screen.getByLabelText("Grad ili destinacija"), listing.city);
  await user.type(screen.getByLabelText("Površina (m²)"), "60");
  await user.type(screen.getByLabelText("Broj soba (0 za garsonjeru)"), "2");
  await user.type(screen.getByLabelText("Cena / mesec"), "850");
  await user.type(screen.getByLabelText("Opis"), listing.description);
  await user.type(screen.getByLabelText(/Javna kontakt email adresa/), listing.contact_email);
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Sačuvaj oglas" }));
  const { id, ...input } = listing;
  await waitFor(() => expect(api.createProperty).toHaveBeenCalledWith({ ...input, seasonal_rates: [], preparation_days: 0, advance_notice_days: 1, booking_window_days: 365, deposit_cents: null, monthly_bills_cents: null, available_from: null, minimum_rental_months: null, pets_policy: null, property_type: null, neighborhood: null, floor: null, heating: null, furnishing: null, has_elevator: null, has_parking: null, has_terrace: null, check_in_time: null, check_out_time: null, booking_enabled: false, max_guests: 2, minimum_nights: 1, maximum_nights: 90, timezone: "Europe/Belgrade" }));
  await user.click(await screen.findByRole("button", { name: `Izmeni: ${listing.title}` }));
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Sačuvaj oglas" }));
  await waitFor(() => expect(api.updateProperty).toHaveBeenCalledWith(id, { ...input, seasonal_rates: [], preparation_days: 0, advance_notice_days: 1, booking_window_days: 365, deposit_cents: null, monthly_bills_cents: null, available_from: null, minimum_rental_months: null, pets_policy: null, property_type: null, neighborhood: null, floor: null, heating: null, furnishing: null, has_elevator: null, has_parking: null, has_terrace: null, is_published: false, check_in_time: null, check_out_time: null, booking_enabled: false, max_guests: 2, minimum_nights: 1, maximum_nights: 90, timezone: "Europe/Belgrade" }));
});
