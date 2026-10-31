import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import OccupancySync, { type CalendarSyncStatus } from "./OccupancySync";

vi.mock("./api", () => ({ api: { occupancySyncStatus: vi.fn(), configureOccupancySync: vi.fn() } }));
afterEach(() => { vi.resetAllMocks(); vi.useRealTimers(); });
const status: CalendarSyncStatus = { available: true, configured: false, enabled: false, allow_empty: false, running: false, next_run_at: null, last_attempt_at: null, last_success_at: null, last_status: "unconfigured" };
const props = { propertyId: 7, sourceId: 4, busy: false, onBusy: vi.fn(), onChanged: vi.fn() };

it("requires explicit consent, defaults to empty-feed protection and clears the private URL", async () => {
  vi.mocked(api.occupancySyncStatus).mockResolvedValue(status);
  vi.mocked(api.configureOccupancySync).mockResolvedValue({ ...status, configured: true, enabled: true, last_status: "pending" });
  render(<OccupancySync {...props} />);
  expect(api.occupancySyncStatus).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Podesi automatsko osvežavanje"));
  const input = await screen.findByLabelText("HTTPS link za automatsko osvežavanje");
  fireEvent.change(input, { target: { value: "https://calendar.example/private" } });
  fireEvent.click(screen.getByText("Poveži i uključi automatiku"));
  expect(api.configureOccupancySync).not.toHaveBeenCalled();
  await waitFor(() => expect(screen.getByText("Odustani od podešavanja")).toHaveFocus());
  fireEvent.click(screen.getByText("Potvrdi podešavanje automatike"));
  expect(await screen.findByText("Podešavanje je sačuvano.")).toBeVisible();
  expect(api.configureOccupancySync).toHaveBeenCalledWith(7, 4, "connect", "https://calendar.example/private", false);
  expect(input).toHaveValue("");
  fireEvent.click(screen.getByText("Pauziraj automatiku"));
  await waitFor(() => expect(api.configureOccupancySync).toHaveBeenLastCalledWith(7, 4, "pause", undefined, false));
});

it("shows worker errors and requires confirmation to disconnect while retaining blocks", async () => {
  vi.mocked(api.occupancySyncStatus).mockResolvedValue({ ...status, configured: true, enabled: true, last_status: "blocked_empty" });
  vi.mocked(api.configureOccupancySync).mockResolvedValue(status);
  render(<OccupancySync {...props} />);
  fireEvent.click(screen.getByText("Podesi automatsko osvežavanje"));
  expect(await screen.findByText(/Prazan snimak bi uklonio/)).toBeVisible();
  fireEvent.click(screen.getByText("Ukloni sačuvani link"));
  expect(screen.getByText(/Postojeće blokade ostaju/)).toBeVisible();
  expect(api.configureOccupancySync).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Potvrdi podešavanje automatike"));
  expect(await screen.findByText("Podešavanje je sačuvano.")).toBeVisible();
  expect(api.configureOccupancySync).toHaveBeenCalledWith(7, 4, "disconnect", undefined, false);
});

it("polls status, handles retry and aborts requests when closed", async () => {
  vi.useFakeTimers();
  vi.mocked(api.occupancySyncStatus).mockRejectedValueOnce(new Error("offline")).mockResolvedValue({ ...status, configured: true, enabled: true, last_status: "applied" });
  const view = render(<OccupancySync {...props} />);
  await act(async () => { fireEvent.click(screen.getByText("Podesi automatsko osvežavanje")); });
  expect(screen.getByRole("alert")).toHaveTextContent("Status nije učitan");
  await act(async () => { fireEvent.click(screen.getByText("Osveži status automatike")); });
  expect(screen.getByText(/Poslednje automatsko osvežavanje je uspelo/)).toBeVisible();
  await act(async () => { vi.advanceTimersByTime(30_000); });
  expect(api.occupancySyncStatus).toHaveBeenCalledTimes(3);
  const signal = vi.mocked(api.occupancySyncStatus).mock.calls[2][2];
  view.unmount();
  expect(signal?.aborted).toBe(true);
  expect(vi.getTimerCount()).toBe(0);
});

it("does not allow activation when the server switch is disabled", async () => {
  vi.mocked(api.occupancySyncStatus).mockResolvedValue({ ...status, available: false });
  render(<OccupancySync {...props} />);
  fireEvent.click(screen.getByText("Podesi automatsko osvežavanje"));
  fireEvent.change(await screen.findByLabelText("HTTPS link za automatsko osvežavanje"), { target: { value: "https://calendar.example/private" } });
  expect(screen.getByText("Poveži i uključi automatiku")).toBeDisabled();
});
