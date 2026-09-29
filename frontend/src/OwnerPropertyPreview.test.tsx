import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import OwnerPropertyPreview from "./OwnerPropertyPreview";

vi.mock("./api", () => ({ api: { ownerProperty: vi.fn(), ownerPhotos: vi.fn(), ownerPhotoBlob: vi.fn() }, ApiError: class extends Error { constructor(message: string, public status: number) { super(message); } } }));
const listing = { id: 7, venue_id: 1, title: "Privatni nacrt", city: "Novi Sad", description: "Stan za dugoročni najam sa terasom.", offer_type: "long_term" as const, area_sqm: 60, rooms: 2, price_cents: 60000, currency: "EUR" as const, contact_email: "owner@example.com", is_published: false, deposit_cents: 0 };
beforeEach(() => { vi.resetAllMocks(); vi.mocked(api.ownerProperty).mockResolvedValue(listing); vi.mocked(api.ownerPhotos).mockResolvedValue([]); });

it("shows a saved private draft and terms without public actions", async () => {
  render(<OwnerPropertyPreview id="7" />);
  expect(await screen.findByRole("heading", { name: listing.title })).toBeVisible();
  expect(api.ownerProperty).toHaveBeenCalledWith(7, expect.any(AbortSignal));
  expect(screen.getByText(/Nacrt — nije u javnoj ponudi/)).toBeVisible();
  expect(screen.getByText("Depozit: Bez depozita")).toBeVisible();
  expect(screen.queryByRole("button", { name: /Pošalji upit|Kopiraj link|Potvrdi rezervaciju/ })).not.toBeInTheDocument();
  expect(await screen.findByText("Fotografije još nisu dodate.")).toBeVisible();
});

it.each(["0", "nope", "9007199254740992"])("rejects invalid ID %s", id => {
  render(<OwnerPropertyPreview id={id} />);
  expect(screen.getByRole("alert")).toHaveTextContent("Link oglasa nije ispravan");
  expect(api.ownerProperty).not.toHaveBeenCalled();
});

it("does not request photos when access is denied and permits retry", async () => {
  vi.mocked(api.ownerProperty).mockRejectedValueOnce(new ApiError("Denied", 403));
  const user = userEvent.setup();
  render(<OwnerPropertyPreview id="7" />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Prijavi se kao vlasnik");
  expect(api.ownerPhotos).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Pokušaj ponovo" }));
  expect(await screen.findByRole("heading", { name: listing.title })).toBeVisible();
});

it("keeps the listing visible when photos fail and aborts on exit", async () => {
  vi.mocked(api.ownerPhotos).mockRejectedValue(new Error("Offline"));
  const view = render(<OwnerPropertyPreview id="7" />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Fotografije nisu učitane");
  expect(screen.getByRole("heading", { name: listing.title })).toBeVisible();
  const signal = vi.mocked(api.ownerProperty).mock.calls[0][1];
  view.unmount();
  expect(signal?.aborted).toBe(true);
});
