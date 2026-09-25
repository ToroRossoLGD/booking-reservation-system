import { act, render, screen, waitFor } from "@testing-library/react";
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
  await waitFor(() => expect(api.properties).toHaveBeenLastCalledWith("Novi Sad", "sale", 0, expect.any(AbortSignal), expect.objectContaining({ sort: "newest" })));
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

it("does not let an older search response overwrite the latest results", async () => {
  let resolveOld!: (value: Awaited<ReturnType<typeof api.properties>>) => void;
  vi.mocked(api.properties).mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve; }));
  const user = userEvent.setup(); render(<PropertyHome />);
  const oldSignal = vi.mocked(api.properties).mock.calls[0][3];
  await user.click(screen.getByRole("button", { name: "Prodaja" }));
  expect(await screen.findByRole("heading", { name: listing.title })).toBeVisible();
  expect(oldSignal?.aborted).toBe(true);
  await act(async () => resolveOld({ items: [{ ...listing, title: "Zastareo rezultat" }], total: 1, limit: 12, offset: 0, has_next: false }));
  expect(screen.queryByRole("heading", { name: "Zastareo rezultat" })).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: listing.title })).toBeVisible();
});

it("restores filters from a URL but does not share unsubmitted location edits", async () => {
  window.history.replaceState(null, "", "/?city=Novi+Sad&offer_type=sale&rooms=0&offset=12");
  const user = userEvent.setup(); render(<PropertyHome />);
  await screen.findByRole("heading", { name: listing.title });
  expect(api.properties).toHaveBeenLastCalledWith("Novi Sad", "sale", 12, expect.any(AbortSignal), { rooms: 0 });
  const input = screen.getByPlaceholderText("Grad ili destinacija");
  await user.clear(input); await user.type(input, "Beograd");
  expect(new URLSearchParams(window.location.search).get("city")).toBe("Novi Sad");
  expect(api.properties).toHaveBeenCalledTimes(1);
  const copy = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
  await user.click(screen.getByRole("button", { name: "Kopiraj link pretrage" }));
  expect(copy).toHaveBeenCalledWith(`${window.location.origin}/?city=Novi+Sad&offer_type=sale&rooms=0&offset=12`);
  await user.click(screen.getByRole("button", { name: /Pretraži ponudu/ }));
  await waitFor(() => expect(api.properties).toHaveBeenLastCalledWith("Beograd", "sale", 0, expect.any(AbortSignal), { rooms: 0 }));
});
