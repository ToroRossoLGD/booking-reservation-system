import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import PropertyHome from "./PropertyHome";
import { api } from "./api";

vi.mock("./api", () => ({ api: { properties: vi.fn() } }));
const listing = { id: 7, title: "Stan pored reke", city: "Novi Sad", offer_type: "sale" as const, area_sqm: 60, rooms: 2, price_cents: 14000000, currency: "EUR" as const, venue_id: 1, description: "Svetao stan sa terasom blizu reke.", contact_email: "owner@example.com", is_published: true };
beforeEach(() => { vi.resetAllMocks(); vi.mocked(api.properties).mockResolvedValue({ items: [listing], total: 1, limit: 12, offset: 0, has_next: false }); Element.prototype.scrollIntoView = vi.fn(); });

it("loads real listings, filters by city and offer, and exposes the owner's contact", async () => {
  const user = userEvent.setup(); render(<PropertyHome />);
  expect(await screen.findByRole("heading", { name: listing.title })).toBeVisible();
  expect(screen.queryByText("Jutro iznad borova")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Prodaja" }));
  await user.type(screen.getByPlaceholderText("Grad ili destinacija"), "Novi Sad");
  await user.click(screen.getByRole("button", { name: /Pretraži ponudu/ }));
  await waitFor(() => expect(api.properties).toHaveBeenLastCalledWith("Novi Sad", "sale", 0, expect.any(AbortSignal)));
  await user.click(await screen.findByRole("button", { name: `Detalji: ${listing.title}` }));
  expect(screen.getByText(listing.description)).toBeVisible();
  expect(screen.getByRole("link", { name: /Kontaktiraj vlasnika/ })).toHaveAttribute("href", expect.stringContaining("mailto:owner%40example.com"));
});

it("distinguishes unavailable API from empty results and can retry", async () => {
  vi.mocked(api.properties).mockRejectedValueOnce(new Error("offline"));
  const user = userEvent.setup(); render(<PropertyHome />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Ponuda trenutno nije dostupna");
  expect(screen.queryByText("Nema oglasa za ovaj izbor.")).not.toBeInTheDocument();
  vi.mocked(api.properties).mockResolvedValue({ items: [], total: 0, limit: 12, offset: 0, has_next: false });
  await user.click(screen.getByRole("button", { name: "Pokušaj ponovo" }));
  expect(await screen.findByText("Nema oglasa za ovaj izbor.")).toBeVisible();
});
