import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import StayBlockManager from "./StayBlockManager";
import { api, ApiError } from "./api";
import { propertyToday, shiftDate } from "./stay-types";

vi.mock("./api", () => ({ api: { stayBlocks: vi.fn(), createStayBlock: vi.fn(), removeStayBlock: vi.fn() }, ApiError: class extends Error { status: number; constructor(message: string, status: number) { super(message); this.status = status; } } }));
const property = { id: 7, venue_id: 1, title: "Stan na dan", description: "Ceo stan za odmor i posao.", city: "Beograd", offer_type: "short_stay" as const, area_sqm: 50, rooms: 2, price_cents: 6500, currency: "EUR" as const, contact_email: "owner@example.com", is_published: true, timezone: "Europe/Belgrade" };
const block = { id: 1, venue_id: 1, check_in: propertyToday(), check_out: shiftDate(propertyToday(), 2), reason: "Renoviranje", active: true, created_at: new Date().toISOString() };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.stayBlocks).mockResolvedValue({ items: [], total: 0, has_next: false });
  vi.mocked(api.createStayBlock).mockResolvedValue(block);
  vi.mocked(api.removeStayBlock).mockResolvedValue(undefined);
});

it("reuses request IDs after failure and submits a private block", async () => {
  vi.mocked(api.createStayBlock).mockRejectedValueOnce(new Error("offline")).mockResolvedValue(block);
  const user = userEvent.setup(); render(<StayBlockManager property={property} />);
  await user.type(screen.getByLabelText("Privatni razlog (opciono)"), "Renoviranje");
  fireEvent.change(screen.getByLabelText("Kraj blokade"), { target: { value: block.check_out } });
  await user.click(screen.getByRole("button", { name: "Blokiraj termin" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Blokada nije sačuvana");
  await user.click(screen.getByRole("button", { name: "Blokiraj termin" }));
  await screen.findByText("Termin je blokiran.");
  expect(vi.mocked(api.createStayBlock).mock.calls[0]).toEqual(vi.mocked(api.createStayBlock).mock.calls[1]);
  expect(api.createStayBlock).toHaveBeenCalledWith(7, expect.objectContaining({ check_in: block.check_in, check_out: block.check_out, reason: "Renoviranje" }));
});

it("requires confirmation before removing a block and refreshes the list", async () => {
  vi.mocked(api.stayBlocks).mockResolvedValueOnce({ items: [block], total: 1, has_next: false }).mockResolvedValue({ items: [], total: 0, has_next: false });
  const user = userEvent.setup(); render(<StayBlockManager property={property} />);
  await user.click(await screen.findByRole("button", { name: "Ukloni blokadu" }));
  expect(api.removeStayBlock).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Potvrdi uklanjanje" }));
  await waitFor(() => expect(api.removeStayBlock).toHaveBeenCalledWith(7, 1));
  await screen.findByText("Aktivnih blokada: 0");
});

it("reports reservation conflicts without clearing the owner's input", async () => {
  vi.mocked(api.createStayBlock).mockRejectedValue(new ApiError("Conflict", 409));
  const user = userEvent.setup(); render(<StayBlockManager property={property} />);
  await user.type(screen.getByLabelText("Privatni razlog (opciono)"), "Sopstveni boravak");
  await user.click(screen.getByRole("button", { name: "Blokiraj termin" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Termin se preklapa");
  expect(screen.getByLabelText("Privatni razlog (opciono)")).toHaveValue("Sopstveni boravak");
});
