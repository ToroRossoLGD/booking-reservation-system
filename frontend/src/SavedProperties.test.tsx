import { useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import PropertyHome from "./PropertyHome";
import SavePropertyButton from "./SavePropertyButton";
import SavedPropertiesPage from "./SavedPropertiesPage";

vi.mock("./api", () => ({ api: { properties: vi.fn(), savedProperties: vi.fn(), savedPropertyIds: vi.fn(), saveProperty: vi.fn(), unsaveProperty: vi.fn() }, ApiError: class extends Error { status: number; constructor(message: string, status: number) { super(message); this.status = status; } } }));
const property = { id: 1, venue_id: 1, title: "Stan za najam", description: "Svetao stan u centru grada.", city: "Beograd", offer_type: "long_term" as const, area_sqm: 50, rooms: 2, price_cents: 60000, currency: "EUR" as const, contact_email: "owner@example.com", is_published: true };
const page = { items: [property], total: 1, limit: 12, offset: 0, has_next: false };
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear();
  vi.mocked(api.properties).mockResolvedValue(page);
  vi.mocked(api.savedProperties).mockResolvedValue(page);
  vi.mocked(api.savedPropertyIds).mockResolvedValue({ property_ids: [] });
  vi.mocked(api.saveProperty).mockResolvedValue({ property_id: 1, saved: true });
  vi.mocked(api.unsaveProperty).mockResolvedValue(undefined);
});
function Button() {
  const [saved, setSaved] = useState(false);
  return <SavePropertyButton propertyId={1} title={property.title} saved={saved} onChange={setSaved} />;
}

it("asks guests to sign in without sending a save request", async () => {
  const user = userEvent.setup();
  render(<Button />);
  await user.click(screen.getByRole("button", { name: /Sačuvaj oglas/ }));
  expect(screen.getByRole("link", { name: "Prijavi se" })).toHaveAttribute("href", "/account");
  expect(api.saveProperty).not.toHaveBeenCalled();
});

it("updates saved state only after success and preserves it after an error", async () => {
  localStorage.setItem("bookica_token", "test");
  vi.mocked(api.saveProperty).mockRejectedValueOnce(new Error("offline")).mockResolvedValue({ property_id: 1, saved: true });
  const user = userEvent.setup();
  render(<Button />);
  await user.click(screen.getByRole("button", { name: /Sačuvaj oglas/ }));
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: /Sačuvaj oglas/ })).toHaveAttribute("aria-pressed", "false");
  await user.click(screen.getByRole("button", { name: /Sačuvaj oglas/ }));
  const saved = await screen.findByRole("button", { name: /Ukloni iz sačuvanih/ });
  expect(saved).toHaveAttribute("aria-pressed", "true");
  await user.click(saved);
  await waitFor(() => expect(api.unsaveProperty).toHaveBeenCalledWith(1));
  expect(screen.getByRole("button", { name: /Sačuvaj oglas/ })).toHaveAttribute("aria-pressed", "false");
});

it("keeps the public catalog visible when saved-status loading fails", async () => {
  localStorage.setItem("bookica_token", "test");
  vi.mocked(api.savedPropertyIds).mockRejectedValue(new Error("offline"));
  render(<PropertyHome />);
  expect(await screen.findByRole("heading", { name: property.title })).toBeVisible();
  expect(await screen.findByRole("alert")).toHaveTextContent("Status sačuvanih oglasa nije učitan");
  expect(screen.getByRole("button", { name: /Sačuvaj oglas/ })).toBeDisabled();
});

it("loads saved status for the visible catalog in one request", async () => {
  localStorage.setItem("bookica_token", "test");
  vi.mocked(api.properties).mockResolvedValue({ ...page, items: [property, { ...property, id: 2, title: "Drugi stan" }], total: 2 });
  vi.mocked(api.savedPropertyIds).mockResolvedValue({ property_ids: [1] });
  render(<PropertyHome />);
  await screen.findByRole("button", { name: `Ukloni iz sačuvanih: ${property.title}` });
  expect(api.savedPropertyIds).toHaveBeenCalledTimes(1);
  expect(api.savedPropertyIds).toHaveBeenCalledWith([1, 2], expect.anything());
  expect(screen.getByRole("button", { name: "Sačuvaj oglas: Drugi stan" })).toHaveAttribute("aria-pressed", "false");
});

it("returns to the previous page after removing the last item on a later page", async () => {
  localStorage.setItem("bookica_token", "test");
  const firstPage = { ...page, items: Array.from({ length: 12 }, (_, i) => ({ ...property, id: i + 1, title: `Stan ${i + 1}` })), total: 13, has_next: true };
  vi.mocked(api.savedProperties).mockResolvedValueOnce(firstPage).mockResolvedValueOnce({ ...page, items: [{ ...property, id: 13 }], offset: 12, total: 13 }).mockResolvedValue({ ...firstPage, total: 12, has_next: false });
  const user = userEvent.setup();
  render(<SavedPropertiesPage />);
  await user.click(await screen.findByRole("button", { name: "Sledeća" }));
  await user.click(await screen.findByRole("button", { name: `Ukloni iz sačuvanih: ${property.title}` }));
  await screen.findByRole("heading", { name: "Stan 1" });
  expect(api.unsaveProperty).toHaveBeenCalledWith(13);
  expect(api.savedProperties).toHaveBeenLastCalledWith(0, expect.anything());
});

it("shows login and empty states on the saved page", async () => {
  vi.mocked(api.savedProperties).mockRejectedValueOnce(new ApiError("Unauthorized", 401)).mockResolvedValue({ ...page, items: [], total: 0 });
  const user = userEvent.setup();
  render(<SavedPropertiesPage />);
  expect(await screen.findByRole("link", { name: "Prijavi se" })).toHaveAttribute("href", "/account");
  await user.click(screen.getByRole("button", { name: "Pokušaj ponovo" }));
  await screen.findByRole("heading", { name: "Još nema sačuvanih oglasa za prikaz." });
  expect(screen.getByRole("link", { name: "Istraži ponudu" })).toHaveAttribute("href", "/");
});
