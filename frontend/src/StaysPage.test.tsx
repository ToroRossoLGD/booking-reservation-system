import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api } from "./api";
import StaysPage from "./StaysPage";
import type { StayPage } from "./stay-types";

vi.mock("./api", () => ({ api: { myStays: vi.fn() }, ApiError: class extends Error {} }));
const page: StayPage = { items: [], total: 25, has_next: true, arrivals_today: 23, departures_today: 2, properties: [{ id: 7, title: "Stan na reci" }] };
beforeEach(() => { vi.resetAllMocks(); vi.mocked(api.myStays).mockResolvedValue(page); });

it("uses server-wide counts and resets pagination when changing owner filters", async () => {
  const user = userEvent.setup(); render(<StaysPage owner />);
  expect(await screen.findByRole("button", { name: "Danas dolaze 23" })).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Sledeća" }));
  await waitFor(() => expect(api.myStays).toHaveBeenLastCalledWith(true, 20, {}, expect.any(AbortSignal)));
  await user.selectOptions(screen.getByLabelText("Stan"), "7");
  await waitFor(() => expect(api.myStays).toHaveBeenLastCalledWith(true, 0, { property_id: 7 }, expect.any(AbortSignal)));
  await user.click(await screen.findByRole("button", { name: "Danas dolaze 23" }));
  await waitFor(() => expect(api.myStays).toHaveBeenLastCalledWith(true, 0, { property_id: 7, day: "arrivals", status: undefined }, expect.any(AbortSignal)));
  await user.selectOptions(screen.getByLabelText("Status"), "cancelled");
  await waitFor(() => expect(api.myStays).toHaveBeenLastCalledWith(true, 0, { property_id: 7, day: undefined, status: "cancelled" }, expect.any(AbortSignal)));
  await user.click(screen.getByRole("button", { name: "Poništi filtere" }));
  await waitFor(() => expect(api.myStays).toHaveBeenLastCalledWith(true, 0, {}, expect.any(AbortSignal)));
});

it("keeps owner filters out of the guest page", async () => {
  render(<StaysPage />);
  await screen.findByText("Ukupno: 25");
  expect(screen.queryByLabelText("Stan")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Danas dolaze/ })).not.toBeInTheDocument();
});

it("ignores an old response after changing filters and aborts it", async () => {
  let resolveOld!: (value: StayPage) => void;
  vi.mocked(api.myStays).mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }));
  const user = userEvent.setup(); render(<StaysPage owner />);
  const oldSignal = vi.mocked(api.myStays).mock.calls[0][3]!;
  await user.selectOptions(screen.getByLabelText("Status"), "confirmed");
  await screen.findByText("Ukupno: 25");
  expect(oldSignal.aborted).toBe(true);
  resolveOld({ ...page, total: 999 });
  await waitFor(() => expect(screen.queryByText("Ukupno: 999")).not.toBeInTheDocument());
});
