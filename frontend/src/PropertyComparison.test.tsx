import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import PropertyComparison from "./PropertyComparison";
import { comparisonRestriction } from "./property-comparison";
import type { PropertyListing } from "./property-types";

const listing: PropertyListing = { id: 1, venue_id: 1, title: "Stan A", description: "Stan u centru", city: "Beograd", offer_type: "long_term", area_sqm: 40, rooms: 0, price_cents: 50000, currency: "EUR", contact_email: "owner@example.com", is_published: true, deposit_cents: 0, has_parking: false, floor: 0 };
it("rejects mixed offers, mixed currencies and a fourth listing but always allows removal", () => {
  expect(comparisonRestriction([listing], { ...listing, id: 2, currency: "RSD" })).not.toBe("");
  expect(comparisonRestriction([listing], { ...listing, id: 2, offer_type: "sale" })).not.toBe("");
  const items = [listing, { ...listing, id: 2 }, { ...listing, id: 3 }];
  expect(comparisonRestriction(items, { ...listing, id: 4 })).not.toBe("");
  expect(comparisonRestriction(items, listing)).toBe("");
});
it("compares rental facts without confusing zero, false or missing information", async () => {
  const user = userEvent.setup();
  const remove = vi.fn();
  const clear = vi.fn();
  render(<PropertyComparison items={[listing, { ...listing, id: 2, title: "Stan B", deposit_cents: null, has_parking: null }]} onRemove={remove} onClear={clear} />);
  await user.click(screen.getByRole("button", { name: "Prikaži poređenje" }));
  const deposit = screen.getByRole("rowheader", { name: "Depozit" }).closest("tr")!;
  expect(deposit).toHaveTextContent("0,00");
  expect(deposit).toHaveTextContent("Nije navedeno");
  const parking = screen.getByRole("rowheader", { name: "Parking" }).closest("tr")!;
  expect(within(parking).getByText("Ne")).toBeVisible();
  expect(within(parking).getByText("Nije navedeno")).toBeVisible();
  expect(screen.getByRole("link", { name: "Stan B" })).toHaveAttribute("href", "/properties/2");
  await user.click(screen.getByRole("button", { name: "Ukloni iz poređenja: Stan A" }));
  expect(remove).toHaveBeenCalledWith(1);
  await user.click(screen.getByRole("button", { name: "Očisti poređenje" }));
  expect(clear).toHaveBeenCalledOnce();
});
it("labels nightly prices as base rates even when selected from dated results", async () => {
  const user = userEvent.setup();
  render(<PropertyComparison items={[{ ...listing, offer_type: "short_stay", stay_total_cents: 999999 }, { ...listing, id: 2, offer_type: "short_stay" }]} onRemove={vi.fn()} onClear={vi.fn()} />);
  await user.click(screen.getByRole("button", { name: "Prikaži poređenje" }));
  expect(screen.getByRole("rowheader", { name: "Osnovna cena / noć" })).toBeVisible();
  expect(screen.getByText(/sezonske cene i dostupnost/)).toBeVisible();
  expect(screen.queryByRole("rowheader", { name: "Depozit" })).not.toBeInTheDocument();
});
