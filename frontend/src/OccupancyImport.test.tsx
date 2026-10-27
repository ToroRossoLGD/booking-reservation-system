import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import OccupancyImport, { type OccupancyImportResult } from "./OccupancyImport";

vi.mock("./api", () => ({ api: { importOccupancy: vi.fn() }, ApiError: class extends Error {} }));
afterEach(() => { vi.resetAllMocks(); localStorage.clear(); });
const preview: OccupancyImportResult = { ranges: [{ check_in: "2026-11-01", check_out: "2026-11-04", status: "ready" }], ignored: 0, clipped: 0, applied: false, created: 0 };
async function choose(content = "calendar") {
  const bytes = new TextEncoder().encode(content);
  await act(async () => { fireEvent.change(screen.getByLabelText(/iCal fajl/), { target: { files: [{ size: bytes.length, arrayBuffer: async () => bytes.buffer }] } }); });
}

it("previews without writes, requires confirmation and refreshes blocks after success", async () => {
  const refresh = vi.fn();
  vi.mocked(api.importOccupancy).mockResolvedValueOnce(preview).mockResolvedValueOnce({ ...preview, applied: true, created: 1 });
  render(<OccupancyImport propertyId={7} onImported={refresh} />);
  await choose();
  expect(api.importOccupancy).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Pregledaj uvoz"));
  expect(await screen.findByText(/Nova blokada/)).toBeVisible();
  expect(api.importOccupancy).toHaveBeenLastCalledWith(7, "calendar", false);
  expect(refresh).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Potvrdi uvoz blokada"));
  expect(await screen.findByText(/Uvoz je završen/)).toBeVisible();
  expect(api.importOccupancy).toHaveBeenLastCalledWith(7, "calendar", true);
  expect(refresh).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByText("Zatvori pregled"));
  expect(screen.queryByText(/Uvoz je završen/)).toBeNull();
  expect(screen.getByLabelText(/iCal fajl/)).toHaveFocus();
});

it("reports a conflict appearing at confirmation and requires a new preview", async () => {
  const refresh = vi.fn();
  vi.mocked(api.importOccupancy).mockResolvedValueOnce(preview).mockResolvedValueOnce({ ...preview, ranges: [{ ...preview.ranges[0], status: "conflict" }] });
  render(<OccupancyImport propertyId={7} onImported={refresh} />);
  await choose();
  fireEvent.click(screen.getByText("Pregledaj uvoz"));
  fireEvent.click(await screen.findByText("Potvrdi uvoz blokada"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Nijedan termin nije uvezen");
  expect(screen.getByText("Potvrdi uvoz blokada")).toBeDisabled();
  expect(refresh).not.toHaveBeenCalled();
  await choose("replacement");
  expect(screen.queryByText("Potvrdi uvoz blokada")).toBeNull();
});

it("rejects oversized files and discards results from a replaced account", async () => {
  localStorage.setItem("bookica_token", "first");
  const refresh = vi.fn();
  let resolve!: (value: OccupancyImportResult) => void;
  vi.mocked(api.importOccupancy).mockImplementation(() => new Promise(done => { resolve = done; }));
  render(<OccupancyImport propertyId={7} onImported={refresh} />);
  fireEvent.change(screen.getByLabelText(/iCal fajl/), { target: { files: [{ size: 100_001 }] } });
  expect(screen.getByRole("alert")).toHaveTextContent("100 KB");
  await choose();
  fireEvent.click(screen.getByText("Pregledaj uvoz"));
  expect(screen.getByText("Pregledaj uvoz")).toBeDisabled();
  localStorage.setItem("bookica_token", "second");
  await act(async () => { window.dispatchEvent(new Event("storage")); resolve({ ...preview, applied: true }); });
  expect(screen.queryByText(/Uvoz je završen/)).toBeNull();
  expect(refresh).not.toHaveBeenCalled();
});
