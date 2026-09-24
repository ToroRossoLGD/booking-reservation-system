import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import PropertyDetailPage from "./PropertyDetailPage";
import { api, ApiError } from "./api";

vi.mock("./api", () => ({ api: { property: vi.fn(), savedPropertyIds: vi.fn(), saveProperty: vi.fn() }, ApiError: class extends Error { status: number; constructor(message: string, status: number) { super(message); this.status = status; } } }));
const listing = { id: 7, venue_id: 1, title: "Stan pored reke", city: "Novi Sad", description: "Svetao stan sa terasom blizu reke.", offer_type: "sale" as const, area_sqm: 60, rooms: 0, price_cents: 14000000, currency: "EUR" as const, contact_email: "owner@example.com", is_published: true };
beforeEach(() => { vi.resetAllMocks(); localStorage.clear(); vi.mocked(api.property).mockResolvedValue(listing); });

it("loads a public listing without login and offers a shareable URL", async () => {
  const user = userEvent.setup(); render(<PropertyDetailPage id="7" />);
  expect(await screen.findByRole("heading", { name: listing.title })).toBeVisible();
  expect(document.title).toBe(`${listing.title} | Bookica`);
  expect(screen.getByText(/Garsonjera/)).toBeVisible();
  expect(screen.getByText(listing.description)).toBeVisible();
  expect(screen.getByRole("link", { name: /Kontaktiraj vlasnika/ })).toHaveAttribute("href", expect.stringContaining("mailto:owner%40example.com"));
  expect(api.savedPropertyIds).not.toHaveBeenCalled();
  const copy = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
  await user.click(screen.getByRole("button", { name: "Kopiraj link oglasa" }));
  expect(copy).toHaveBeenCalledWith(`${window.location.origin}/properties/7`);
  expect(screen.getByRole("status")).toHaveTextContent("Link je kopiran.");
  copy.mockRejectedValue(new Error("denied"));
  await user.click(screen.getByRole("button", { name: "Kopiraj link oglasa" }));
  expect(screen.getByLabelText("Kopiraj adresu ručno")).toHaveValue(`${window.location.origin}/properties/7`);
});

it.each(["0", "nope", "7/extra", "9007199254740992"])("rejects invalid ID %s without requesting data", id => {
  render(<PropertyDetailPage id={id} />);
  expect(screen.getByRole("heading", { name: "Oglas nije dostupan." })).toBeVisible();
  expect(api.property).not.toHaveBeenCalled();
});

it("distinguishes withdrawn or missing listings from retryable errors", async () => {
  const user = userEvent.setup();
  vi.mocked(api.property).mockRejectedValueOnce(new Error("offline")).mockRejectedValueOnce(new ApiError("Not found", 404));
  render(<PropertyDetailPage id="7" />);
  await screen.findByRole("alert");
  await user.click(screen.getByRole("button", { name: "Pokušaj ponovo" }));
  expect(await screen.findByRole("heading", { name: "Oglas nije dostupan." })).toBeVisible();
  expect(screen.queryByText(listing.description)).not.toBeInTheDocument();
});

it("keeps listing visible after saved-status failure and retries", async () => {
  localStorage.setItem("bookica_token", "test");
  vi.mocked(api.savedPropertyIds).mockRejectedValueOnce(new Error("offline")).mockResolvedValue({ property_ids: [7] });
  const user = userEvent.setup(); render(<PropertyDetailPage id="7" />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Status sačuvanog oglasa nije učitan");
  expect(screen.getByRole("heading", { name: listing.title })).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Pokušaj ponovo" }));
  await waitFor(() => expect(screen.getByRole("button", { name: /Ukloni iz sačuvanih/ })).toBeEnabled());
});

it("aborts an in-flight request when leaving the page", () => {
  vi.mocked(api.property).mockReturnValue(new Promise(() => {}));
  const view = render(<PropertyDetailPage id="7" />);
  const signal = vi.mocked(api.property).mock.calls[0][1];
  view.unmount();
  expect(signal?.aborted).toBe(true);
});
