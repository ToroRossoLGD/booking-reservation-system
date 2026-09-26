import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import PropertyActions from "./PropertyActions";
import PropertyManager from "./PropertyManager";
import { api } from "./api";
import type { PropertyListing } from "./property-types";

vi.mock("./api", () => ({ api: { ownerProperties: vi.fn(), updateProperty: vi.fn() }, ApiError: class extends Error {} }));
const property: PropertyListing = { id: 1, venue_id: 1, title: "Stan", description: "Udoban stan u centru grada.", city: "Beograd", offer_type: "short_stay", price_cents: 5000, currency: "EUR", area_sqm: 50, rooms: 2, contact_email: "host@example.com", is_published: true, check_in_time: "16:00", check_out_time: "10:00", timezone: "Europe/Belgrade" };

it("shows nightly rules even without online bookings, but hides them for sale and rent", () => {
  const { rerender } = render(<PropertyActions property={property} />);
  expect(screen.getByText(/Prijava od 16:00/)).toHaveTextContent("Odjava do 10:00 (Europe/Belgrade)");
  for (const offer_type of ["sale", "long_term"] as const) {
    rerender(<PropertyActions property={{ ...property, offer_type }} />);
    expect(screen.queryByText(/Prijava od/)).not.toBeInTheDocument();
  }
});

it("edits nightly times and clears them when changing the offer to sale", async () => {
  vi.mocked(api.ownerProperties).mockResolvedValue({ items: [property], total: 1, offset: 0, limit: 20, has_next: false });
  vi.mocked(api.updateProperty).mockResolvedValue(property);
  const user = userEvent.setup();
  render(<PropertyManager venues={[{ id: 1, name: "Stan", description: null, address: "Centar", owner_id: 1 }]} />);
  await user.click(await screen.findByRole("button", { name: "Izmeni: Stan" }));
  expect(screen.getByLabelText("Prijava od")).toHaveValue("16:00");
  expect(screen.getByLabelText("Odjava do")).toHaveValue("10:00");
  await user.selectOptions(screen.getByLabelText("Vrsta ponude"), "sale");
  expect(screen.queryByLabelText("Prijava od")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Sačuvaj oglas" }));
  expect(api.updateProperty).toHaveBeenCalledWith(1, expect.objectContaining({ offer_type: "sale", check_in_time: null, check_out_time: null }));
});
