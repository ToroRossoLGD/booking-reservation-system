import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import OccupancyImport, { type OccupancyImportResult } from "./OccupancyImport";

vi.mock("./api", () => ({ api: { importOccupancy: vi.fn(), fetchOccupancyUrl: vi.fn() }, ApiError: class extends Error {} }));
afterEach(() => { vi.resetAllMocks(); localStorage.clear(); });
const preview: OccupancyImportResult = { ranges: [{ check_in: "2026-11-01", check_out: "2026-11-04", status: "ready" }], ignored: 0, clipped: 0, applied: false, created: 0 };

it("fetches a URL only on demand and confirms the reviewed snapshot without refetching", async () => {
  vi.mocked(api.fetchOccupancyUrl).mockResolvedValue({ content: "sanitized snapshot" });
  vi.mocked(api.importOccupancy).mockResolvedValueOnce(preview).mockResolvedValueOnce({ ...preview, applied: true, created: 1 });
  render(<OccupancyImport propertyId={7} onImported={() => {}} />);
  fireEvent.change(screen.getByLabelText("Privatni iCal HTTPS link"), { target: { value: "https://calendar.example/a?token=secret" } });
  expect(api.fetchOccupancyUrl).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Preuzmi i pregledaj link"));
  expect(await screen.findByText(/Nova blokada/)).toBeVisible();
  expect(screen.getByLabelText("Privatni iCal HTTPS link")).toHaveValue("");
  expect(api.importOccupancy).toHaveBeenLastCalledWith(7, "sanitized snapshot", false);
  fireEvent.click(screen.getByText("Potvrdi uvoz blokada"));
  expect(await screen.findByText(/Uvoz je završen/)).toBeVisible();
  expect(api.importOccupancy).toHaveBeenLastCalledWith(7, "sanitized snapshot", true);
  expect(api.fetchOccupancyUrl).toHaveBeenCalledTimes(1);
});

it("retries download failures and invalidates a preview when its source changes", async () => {
  vi.mocked(api.fetchOccupancyUrl).mockRejectedValueOnce(new Error("network")).mockResolvedValue({ content: "snapshot" });
  vi.mocked(api.importOccupancy).mockResolvedValue(preview);
  render(<OccupancyImport propertyId={7} onImported={() => {}} />);
  fireEvent.change(screen.getByLabelText("Privatni iCal HTTPS link"), { target: { value: "https://calendar.example/a" } });
  fireEvent.click(screen.getByText("Preuzmi i pregledaj link"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Kalendar nije preuzet");
  expect(api.importOccupancy).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Preuzmi i pregledaj link"));
  expect(await screen.findByText("Potvrdi uvoz blokada")).toBeVisible();
  fireEvent.change(screen.getByLabelText("Privatni iCal HTTPS link"), { target: { value: "https://calendar.example/b" } });
  expect(screen.queryByText("Potvrdi uvoz blokada")).toBeNull();
  expect(screen.getByText("Pregledaj uvoz")).toBeDisabled();
});

it("does not preview a downloaded snapshot after an account changes", async () => {
  localStorage.setItem("bookica_token", "first");
  let resolve!: (value: { content: string }) => void;
  vi.mocked(api.fetchOccupancyUrl).mockImplementation(() => new Promise(done => { resolve = done; }));
  render(<OccupancyImport propertyId={7} onImported={() => {}} />);
  fireEvent.change(screen.getByLabelText("Privatni iCal HTTPS link"), { target: { value: "https://calendar.example/a" } });
  fireEvent.click(screen.getByText("Preuzmi i pregledaj link"));
  expect(screen.getByText("Preuzmi i pregledaj link")).toBeDisabled();
  localStorage.setItem("bookica_token", "second");
  await act(async () => { window.dispatchEvent(new Event("storage")); resolve({ content: "old account" }); });
  expect(api.importOccupancy).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Privatni iCal HTTPS link")).toHaveValue("");
});
async function choose(content = "calendar") {
  const bytes = new TextEncoder().encode(content);
  await act(async () => { fireEvent.change(screen.getByLabelText(/iCal fajl/), { target: { files: [{ size: bytes.length, arrayBuffer: async () => bytes.buffer }] } }); });
}

it("shows occupied ranges and their types for a conflict without allowing confirmation", async () => {
  vi.mocked(api.importOccupancy).mockResolvedValue({ ...preview, ranges: [{ ...preview.ranges[0], status: "conflict", conflicts: [
    { check_in: "2026-10-31", check_out: "2026-11-02", kind: "reservation" },
    { check_in: "2026-11-03", check_out: "2026-11-05", kind: "block" },
  ] }] });
  render(<OccupancyImport propertyId={7} onImported={() => {}} />);
  await choose();
  fireEvent.click(screen.getByText("Pregledaj uvoz"));
  expect(await screen.findByText(/Rezervacija ili vreme pripreme:/)).toHaveTextContent("31. 10. 2026.");
  expect(screen.getByText(/Postojeća blokada:/)).toHaveTextContent("5. 11. 2026.");
  expect(screen.getByText("Potvrdi uvoz blokada")).toBeDisabled();
  await choose("new calendar");
  expect(screen.queryByText(/Rezervacija ili vreme pripreme:/)).toBeNull();
});

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
