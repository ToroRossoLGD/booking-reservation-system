import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import CalendarDownloadButton from "./CalendarDownloadButton";

const file = { filename: "bookica-boravak-7.ics", contents: "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n" };
const createObjectURL = vi.fn<(blob: Blob | MediaSource) => string>(() => "blob:calendar-test");
const revokeObjectURL = vi.fn();

beforeEach(() => {
  vi.useFakeTimers(); createObjectURL.mockClear(); revokeObjectURL.mockClear();
  vi.stubGlobal("URL", class extends URL {
    static createObjectURL = createObjectURL;
    static revokeObjectURL = revokeObjectURL;
  });
});
afterEach(() => { vi.runOnlyPendingTimers(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("downloads a calendar with the right name and MIME type, then releases the temporary URL", () => {
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    expect(this.isConnected).toBe(true);
    expect(this.download).toBe(file.filename);
    expect(this.href).toBe("blob:calendar-test");
  });
  const view = render(<CalendarDownloadButton create={() => file} />);
  fireEvent.click(screen.getByRole("button"));
  expect(click).toHaveBeenCalledTimes(1);
  expect(document.querySelector("a[download]")).toBeNull();
  const blob = createObjectURL.mock.calls[0][0] as Blob;
  expect(blob.type).toBe("text/calendar;charset=utf-8");
  expect(blob.size).toBe(new TextEncoder().encode(file.contents).length);
  expect(revokeObjectURL).not.toHaveBeenCalled();
  view.unmount();
  act(() => vi.advanceTimersByTime(1000));
  expect(revokeObjectURL).toHaveBeenCalledExactlyOnceWith("blob:calendar-test");
});

it("allows retry after generation fails without leaving an error on success", () => {
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const create = vi.fn().mockImplementationOnce(() => { throw new Error("invalid date"); }).mockReturnValue(file);
  render(<CalendarDownloadButton create={create} />);
  fireEvent.click(screen.getByRole("button"));
  expect(screen.getByRole("alert")).toHaveTextContent("Preuzimanje nije uspelo");
  expect(createObjectURL).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button"));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(createObjectURL).toHaveBeenCalledTimes(1);
});

it("cleans up the anchor and URL even when the browser blocks the download", () => {
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => { throw new Error("blocked"); });
  render(<CalendarDownloadButton create={() => file} />);
  fireEvent.click(screen.getByRole("button"));
  expect(screen.getByRole("alert")).toBeVisible();
  expect(document.querySelector("a[download]")).toBeNull();
  act(() => vi.advanceTimersByTime(1000));
  expect(revokeObjectURL).toHaveBeenCalledExactlyOnceWith("blob:calendar-test");
});

it("does not create a file when the event is no longer exportable", () => {
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click");
  render(<CalendarDownloadButton create={() => null} />);
  fireEvent.click(screen.getByRole("button"));
  expect(createObjectURL).not.toHaveBeenCalled();
  expect(click).not.toHaveBeenCalled();
});
