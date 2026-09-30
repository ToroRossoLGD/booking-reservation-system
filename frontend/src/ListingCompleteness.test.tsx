import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import PropertyManager from "./PropertyManager";
import { api } from "./api";
import type { PropertyListing } from "./property-types";

vi.mock("./api", () => ({ api: { ownerProperties: vi.fn(), ownerPhotos: vi.fn(), updateProperty: vi.fn() }, ApiError: class extends Error {} }));
const listing: PropertyListing = { id: 7, venue_id: 1, title: "Stan za najam", description: "Udoban stan u centru grada.", city: "Beograd", offer_type: "long_term", area_sqm: 60, rooms: 2, price_cents: 85000, currency: "EUR", contact_email: "owner@example.com", is_published: true, photos: [], deposit_cents: 0, monthly_bills_cents: 0 };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.ownerProperties).mockResolvedValue({ items: [listing], total: 1, limit: 20, offset: 0, has_next: false });
  vi.mocked(api.ownerPhotos).mockResolvedValue([]);
  vi.mocked(api.updateProperty).mockResolvedValue(listing);
});
async function open() {
  const user = userEvent.setup();
  render(<PropertyManager venues={[{ id: 1, name: "Objekat", description: null, address: "Centar", owner_id: 1 }]} />);
  await user.click(await screen.findByRole("button", { name: "Izmeni: Stan za najam" }));
  return user;
}
it("focuses missing fields, updates unsaved hints and treats zero rental costs as supplied", async () => {
  const user = await open();
  const hints = within(screen.getByRole("complementary", { name: "Preporuke za oglas" }));
  expect(hints.queryByText(/Navedi depozit/)).not.toBeInTheDocument();
  expect(hints.queryByText(/Navedi okvirne/)).not.toBeInTheDocument();
  await user.click(hints.getByRole("button", { name: "Navedi grejanje" }));
  expect(screen.getByLabelText("Grejanje")).toHaveFocus();
  await user.selectOptions(screen.getByLabelText("Grejanje"), "gas");
  expect(hints.queryByText("Navedi grejanje")).not.toBeInTheDocument();
  await user.clear(screen.getByLabelText("Depozit"));
  expect(hints.getByText(/Navedi depozit/)).toBeVisible();
  await user.type(screen.getByLabelText("Depozit"), "0");
  expect(hints.queryByText(/Navedi depozit/)).not.toBeInTheDocument();
  expect(api.updateProperty).not.toHaveBeenCalled();
});
it("shows completion for supplied recommendations and resets when opening a new listing", async () => {
  vi.mocked(api.ownerProperties).mockResolvedValue({ items: [{ ...listing, offer_type: "sale", property_type: "apartment", neighborhood: "Centar", heating: "gas", furnishing: "unfurnished", photos: [{ id: 1, property_id: 7, position: 0, width: 800, height: 600 }] }], total: 1, limit: 20, offset: 0, has_next: false });
  const user = await open();
  expect(screen.getByText("Popunjeni su svi preporučeni podaci i dodate su fotografije.")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Novi oglas" }));
  expect(screen.queryByText("Popunjeni su svi preporučeni podaci i dodate su fotografije.")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Navedi grejanje" })).toBeVisible();
});
it("hides rental hints for sale and short stays and permits saving with optional hints", async () => {
  const user = await open();
  expect(screen.getByText("Navedi pravilo za ljubimce")).toBeVisible();
  for (const type of ["short_stay", "sale"]) {
    await user.selectOptions(screen.getByLabelText("Vrsta ponude"), type);
    expect(screen.queryByText("Navedi pravilo za ljubimce")).not.toBeInTheDocument();
  }
  await user.click(screen.getByRole("button", { name: "Sačuvaj oglas" }));
  expect(api.updateProperty).toHaveBeenCalledWith(7, expect.objectContaining({ offer_type: "sale", is_published: true }));
});
it("opens photo management without submitting the form and explains first-save uploads", async () => {
  const user = await open();
  await user.click(screen.getByRole("button", { name: "Dodaj fotografije" }));
  expect(await screen.findByRole("region", { name: "Fotografije: Stan za najam" })).toBeVisible();
  expect(api.updateProperty).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Novi oglas" }));
  expect(screen.getByText("Fotografije dodaješ nakon prvog čuvanja oglasa.")).toBeVisible();
  expect(screen.getByText("Dodaj kontakt email adresu")).toBeVisible();
});
