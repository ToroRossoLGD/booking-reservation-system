import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import PropertyManager from "./PropertyManager";
import { api } from "./api";

vi.mock("./api", () => ({ api: { ownerProperties: vi.fn(), createProperty: vi.fn(), updateProperty: vi.fn() }, ApiError: class extends Error {} }));

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
  await waitFor(() => expect(api.createProperty).toHaveBeenCalledWith({ ...input, check_in_time: null, check_out_time: null, booking_enabled: false, max_guests: 2, minimum_nights: 1, timezone: "Europe/Belgrade" }));
  await user.click(await screen.findByRole("button", { name: `Izmeni: ${listing.title}` }));
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Sačuvaj oglas" }));
  await waitFor(() => expect(api.updateProperty).toHaveBeenCalledWith(id, { ...input, is_published: false, check_in_time: null, check_out_time: null, booking_enabled: false, max_guests: 2, minimum_nights: 1, timezone: "Europe/Belgrade" }));
});
