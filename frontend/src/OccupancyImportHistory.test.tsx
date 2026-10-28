import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import OccupancyImport from "./OccupancyImport";
import OccupancyImportHistory, { type OccupancyImportRun } from "./OccupancyImportHistory";

vi.mock("./api", () => ({ api: { occupancyImportHistory: vi.fn(), importOccupancy: vi.fn() }, ApiError: class extends Error {} }));
afterEach(() => { vi.resetAllMocks(); localStorage.clear(); });
const row: OccupancyImportRun = { id: 1, created_at: "2026-10-28T09:30:00Z", status: "applied", created: 2, existing: 1, conflicts: 0, ignored: 3, clipped: 1 };

it("loads on demand, retries errors and distinguishes conflict and no-op outcomes", async () => {
  vi.mocked(api.occupancyImportHistory).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce([
    { ...row, id: 3, status: "conflict", created: 0, conflicts: 1 }, { ...row, id: 2, created: 0 }, row,
  ]);
  render(<OccupancyImportHistory propertyId={7} revision={0} />);
  expect(api.occupancyImportHistory).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Istorija uvoza kalendara"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Istorija nije učitana");
  fireEvent.click(screen.getByText("Osveži istoriju uvoza"));
  expect(await screen.findByText(/Sprečen uvoz/)).toBeVisible();
  expect(screen.getByText(/Završen uvoz bez novih/)).toBeVisible();
  expect(screen.getByText(/Uspešan uvoz/)).toBeVisible();
  expect(screen.getAllByText(/UTC/)).toHaveLength(3);
  expect(screen.getByText(/Novih blokada: 2/)).toHaveTextContent("Preskočenih događaja: 3");
});

it("reloads after a confirmation and clears old data while loading", async () => {
  vi.mocked(api.occupancyImportHistory).mockResolvedValueOnce([]).mockResolvedValueOnce([row]);
  const view = render(<OccupancyImportHistory propertyId={7} revision={0} />);
  fireEvent.click(screen.getByText("Istorija uvoza kalendara"));
  expect(await screen.findByText(/Još nema/)).toBeVisible();
  view.rerender(<OccupancyImportHistory propertyId={7} revision={1} />);
  expect(await screen.findByText(/Uspešan uvoz/)).toBeVisible();
  expect(api.occupancyImportHistory).toHaveBeenCalledTimes(2);
});

it("discards an old account's pending history and closes it on a session change", async () => {
  localStorage.setItem("bookica_token", "first");
  let resolve!: (value: OccupancyImportRun[]) => void;
  vi.mocked(api.occupancyImportHistory).mockImplementation(() => new Promise(done => { resolve = done; }));
  render(<OccupancyImport propertyId={7} onImported={() => {}} />);
  fireEvent.click(screen.getByText("Istorija uvoza kalendara"));
  const signal = vi.mocked(api.occupancyImportHistory).mock.calls[0][1];
  localStorage.setItem("bookica_token", "second");
  await act(async () => { window.dispatchEvent(new Event("storage")); resolve([row]); });
  expect(signal?.aborted).toBe(true);
  expect(screen.queryByText(/Uspešan uvoz/)).toBeNull();
  expect(screen.getByText("Istorija uvoza kalendara")).toHaveAttribute("aria-expanded", "false");
});
