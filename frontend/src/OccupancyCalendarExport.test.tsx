import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import OccupancyCalendarExport from "./OccupancyCalendarExport";

vi.mock("./api", () => ({ api: { occupancyCalendar: vi.fn() } }));
afterEach(() => { vi.restoreAllMocks(); vi.resetAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); });

it("downloads only after an explicit request and cleans up after retry", async () => {
  const content = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n";
  vi.mocked(api.occupancyCalendar).mockRejectedValueOnce(new Error("offline")).mockResolvedValue(content);
  const create = vi.fn<(blob: Blob | MediaSource) => string>(() => "blob:occupancy");
  const revoke = vi.fn();
  vi.stubGlobal("URL", class extends URL { static createObjectURL = create; static revokeObjectURL = revoke; });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    expect(this.download).toBe("bookica-occupancy-7.ics");
    expect(this.href).toBe("blob:occupancy");
  });
  render(<OccupancyCalendarExport propertyId={7} />);
  expect(api.occupancyCalendar).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Izvoz nije uspeo");
  fireEvent.click(screen.getByRole("button"));
  expect(await screen.findByRole("status")).toHaveTextContent("Preuzimanje je pokrenuto");
  expect(click).toHaveBeenCalledTimes(1);
  expect(create.mock.calls[0][0]).toBeInstanceOf(Blob);
  expect(document.querySelector("a[download]")).toBeNull();
  await waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:occupancy"), { timeout: 2000 });
});

it("blocks duplicate requests and discards a response after the session changes", async () => {
  localStorage.setItem("bookica_token", "first");
  let resolve!: (value: string) => void;
  vi.mocked(api.occupancyCalendar).mockImplementation(() => new Promise(done => { resolve = done; }));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<OccupancyCalendarExport propertyId={7} />);
  fireEvent.click(screen.getByRole("button"));
  fireEvent.click(screen.getByRole("button"));
  expect(screen.getByRole("button")).toBeDisabled();
  expect(api.occupancyCalendar).toHaveBeenCalledTimes(1);
  localStorage.setItem("bookica_token", "second");
  await act(async () => { resolve("private data"); });
  expect(click).not.toHaveBeenCalled();
  expect(screen.getByRole("alert")).toBeVisible();
  expect(screen.getByRole("button")).toBeEnabled();
});
