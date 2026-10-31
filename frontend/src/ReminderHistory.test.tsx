import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import ReminderHistory from "./ReminderHistory";

vi.mock("./api", () => ({ api: { reminderHistory: vi.fn() } }));
afterEach(() => vi.resetAllMocks());
const item = { id: 1, kind: "arrival" as const, reference_id: 7, scheduled_for: "2026-11-02", created_at: "2026-11-01T09:00:00Z" };

it("loads on demand, shows delivery semantics and pages", async () => {
  vi.mocked(api.reminderHistory).mockResolvedValueOnce({ items: [item], offset: 0, has_next: true }).mockResolvedValue({ items: [], offset: 20, has_next: false });
  render(<ReminderHistory viewing={false} />);
  expect(api.reminderHistory).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Istorija isporuke podsetnika" }));
  expect(await screen.findByText("Dolazak · rezervacija #7")).toBeVisible();
  expect(screen.getByText(/Ne potvrđuju čitanje/)).toBeVisible();
  fireEvent.click(screen.getByText("Sledećih 20 podsetnika"));
  expect(await screen.findByText("Nema zabeleženih podsetnika na ovoj stranici.")).toBeVisible();
  expect(api.reminderHistory).toHaveBeenLastCalledWith(false, 20, expect.any(AbortSignal));
  expect(screen.getByText("Sledećih 20 podsetnika")).toBeDisabled();
});

it("retries errors and discards closed-panel responses", async () => {
  vi.mocked(api.reminderHistory).mockRejectedValueOnce(new Error());
  render(<ReminderHistory viewing />);
  const toggle = screen.getByRole("button", { name: "Istorija isporuke podsetnika" });
  fireEvent.click(toggle);
  expect(await screen.findByRole("alert")).toHaveTextContent("Istorija nije učitana");
  let resolve!: (value: { items: typeof item[]; offset: number; has_next: boolean }) => void;
  vi.mocked(api.reminderHistory).mockImplementation(() => new Promise(done => { resolve = done; }));
  fireEvent.click(screen.getByText("Osveži istoriju podsetnika"));
  const signal = vi.mocked(api.reminderHistory).mock.calls[1][2];
  fireEvent.click(toggle);
  await act(async () => resolve({ items: [item], offset: 0, has_next: false }));
  expect(signal?.aborted).toBe(true);
  expect(screen.queryByText("Dolazak · rezervacija #7")).toBeNull();
});
