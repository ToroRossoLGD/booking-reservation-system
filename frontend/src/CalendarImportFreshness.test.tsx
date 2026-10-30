import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import CalendarImportFreshness from "./CalendarImportFreshness";
import type { OccupancySource } from "./OccupancySources";

const now = new Date("2026-10-30T12:00:00Z");
const source: OccupancySource = { id: 1, name: "Channel", revision: 1, last_attempt_at: null, last_success_at: null, last_status: null };
afterEach(() => { vi.useRealTimers(); });

it("distinguishes never-imported and conflicting sources without suggesting live sync", () => {
  const view = render(<CalendarImportFreshness source={source} />);
  expect(screen.getByRole("status")).toHaveTextContent("još nema uspešan uvoz");
  view.rerender(<CalendarImportFreshness source={{ ...source, last_status: "conflict", last_success_at: now.toISOString() }} />);
  expect(screen.getByRole("status")).toHaveTextContent("poslednji pokušaj je imao preklapanje");
  expect(screen.getByText(/Promene se ne preuzimaju automatski/)).toBeVisible();
});

it("becomes stale at 24 hours while open and clears its timer on unmount", () => {
  vi.useFakeTimers(); vi.setSystemTime(now);
  const view = render(<CalendarImportFreshness source={{ ...source, last_success_at: "2026-10-29T12:01:00Z" }} />);
  expect(screen.getByRole("status")).toHaveTextContent("u poslednja 24 sata");
  act(() => { vi.advanceTimersByTime(60_000); });
  expect(screen.getByRole("status")).toHaveTextContent("star najmanje 24 sata");
  view.unmount();
  expect(vi.getTimerCount()).toBe(0);
});

it("updates after a new successful import and refreshes the clock on window focus", () => {
  vi.useFakeTimers(); vi.setSystemTime(now);
  const view = render(<CalendarImportFreshness source={{ ...source, last_success_at: "2026-10-28T12:00:00Z" }} />);
  expect(screen.getByRole("status")).toHaveTextContent("star najmanje 24 sata");
  view.rerender(<CalendarImportFreshness source={{ ...source, last_success_at: now.toISOString() }} />);
  expect(screen.getByRole("status")).toHaveTextContent("u poslednja 24 sata");
  vi.setSystemTime(new Date("2026-11-01T12:00:00Z"));
  act(() => { window.dispatchEvent(new Event("focus")); });
  expect(screen.getByRole("status")).toHaveTextContent("star najmanje 24 sata");
});

it("does not label malformed or future timestamps as recent", () => {
  vi.useFakeTimers(); vi.setSystemTime(now);
  const view = render(<CalendarImportFreshness source={{ ...source, last_success_at: "invalid" }} />);
  expect(screen.getByRole("status")).toHaveTextContent("nije pouzdano utvrđena");
  view.rerender(<CalendarImportFreshness source={{ ...source, last_success_at: "2026-11-01T12:00:00Z" }} />);
  expect(screen.getByRole("status")).toHaveTextContent("nije pouzdano utvrđena");
});
