import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import OccupancyImport from "./OccupancyImport";
import type { OccupancySource } from "./OccupancySources";

vi.mock("./api", () => ({ api: { occupancySources: vi.fn(), createOccupancySource: vi.fn(), removeOccupancySource: vi.fn(), importOccupancy: vi.fn() }, ApiError: class extends Error {} }));
afterEach(() => { vi.resetAllMocks(); localStorage.clear(); });
const source: OccupancySource = { id: 4, name: "Channel A", revision: 2, last_attempt_at: null, last_success_at: null, last_status: null };
async function file() {
  const bytes = new TextEncoder().encode("empty calendar");
  await act(async () => { fireEvent.change(screen.getByLabelText(/iCal fajl/), { target: { files: [{ size: bytes.length, arrayBuffer: async () => bytes.buffer }] } }); });
}

it("requires a fresh preview for a source, shows removals and confirms the preview revision", async () => {
  vi.mocked(api.occupancySources).mockResolvedValue([source]);
  vi.mocked(api.importOccupancy).mockResolvedValueOnce({ ranges: [], ignored: 0, clipped: 0, applied: false, created: 0, removed: 1, source_revision: 2, removed_ranges: [{ check_in: "2026-11-01", check_out: "2026-11-03" }] })
    .mockResolvedValueOnce({ ranges: [], ignored: 0, clipped: 0, applied: true, created: 0, removed: 1, source_revision: 3 });
  render(<OccupancyImport propertyId={7} onImported={() => {}} />);
  expect(api.occupancySources).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Uvoz po izvoru kalendara"));
  await screen.findByText("Channel A");
  fireEvent.change(screen.getByLabelText("Izvor za ovaj uvoz"), { target: { value: "4" } });
  await file();
  fireEvent.click(screen.getByText("Pregledaj uvoz"));
  expect(await screen.findByLabelText("Blokade izvora za uklanjanje")).toHaveTextContent("1. 11. 2026.");
  expect(screen.getByText("Potvrdi uvoz blokada")).toBeEnabled();
  fireEvent.click(screen.getByText("Potvrdi uvoz blokada"));
  expect(await screen.findByText(/Uvoz je završen/)).toBeVisible();
  expect(api.importOccupancy).toHaveBeenLastCalledWith(7, "empty calendar", true, 4, 2);
});

it("creates a named source and requires explicit confirmation to remove its blocks", async () => {
  vi.mocked(api.occupancySources).mockResolvedValueOnce([]).mockResolvedValueOnce([source]).mockResolvedValue([]);
  vi.mocked(api.createOccupancySource).mockResolvedValue(source);
  vi.mocked(api.removeOccupancySource).mockResolvedValue();
  const refresh = vi.fn();
  render(<OccupancyImport propertyId={7} onImported={refresh} />);
  fireEvent.click(screen.getByText("Uvoz po izvoru kalendara"));
  await act(async () => {});
  fireEvent.change(screen.getByLabelText("Naziv novog izvora (bez linka)"), { target: { value: "Channel A" } });
  fireEvent.click(screen.getByText("Dodaj izvor"));
  fireEvent.click(await screen.findByText("Ukloni izvor i njegove blokade"));
  expect(api.removeOccupancySource).not.toHaveBeenCalled();
  expect(screen.getByText("Odustani od uklanjanja izvora")).toHaveFocus();
  fireEvent.click(screen.getByText("Potvrdi uklanjanje izvora"));
  await act(async () => {});
  expect(api.removeOccupancySource).toHaveBeenCalledWith(7, 4);
  expect(refresh).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText("Izvor za ovaj uvoz")).toHaveValue("");
});
