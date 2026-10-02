import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import SavedSearches from "./SavedSearches";
import { normalizedSearchPath, readSavedSearches, SAVED_SEARCHES_KEY } from "./saved-searches";

beforeEach(() => localStorage.clear());
afterEach(() => { vi.restoreAllMocks(); localStorage.clear(); });

it("saves filters from page one, restores after remount and renames instead of duplicating", async () => {
  const user = userEvent.setup();
  const view = render(<SavedSearches path="/?city=Novi+Sad&offer_type=long_term&currency=EUR&max_price_cents=60000&rooms=0&has_parking=false&offset=24" />);
  await user.type(screen.getByLabelText("Naziv pretrage"), "Moj stan");
  await user.click(screen.getByRole("button", { name: "Sačuvaj trenutnu pretragu" }));
  const path = screen.getByRole("link", { name: "Moj stan" }).getAttribute("href")!;
  expect(path).not.toContain("offset");
  expect(path).toContain("rooms=0");
  expect(path).toContain("has_parking=false");
  expect(path).toContain("max_price_cents=60000");
  view.unmount();
  render(<SavedSearches path={path} />);
  expect(screen.getByRole("link", { name: "Moj stan" })).toHaveAttribute("href", path);
  await user.type(screen.getByLabelText("Naziv pretrage"), "Novo ime");
  await user.click(screen.getByRole("button", { name: "Promeni naziv sačuvane pretrage" }));
  expect(readSavedSearches()).toEqual([{ name: "Novo ime", path }]);
  await user.click(screen.getByRole("button", { name: "Ukloni pretragu: Novo ime" }));
  expect(readSavedSearches()).toEqual([]);
});

it("retains dated searches and rejects unsafe stored URLs", () => {
  const path = "/?offer_type=short_stay&check_in=2030-10-01&check_out=2030-10-04&guests=2";
  expect(normalizedSearchPath(path)).toBe(path);
  localStorage.setItem(SAVED_SEARCHES_KEY, JSON.stringify([
    { name: "Bad", path: "//example.com" }, { name: "Bad", path: "javascript:alert(1)" },
    { name: "Dates", path }, { name: "Duplicate", path }, { name: null, path: "/" },
  ]));
  expect(readSavedSearches()).toEqual([{ name: "Dates", path }]);
  localStorage.setItem(SAVED_SEARCHES_KEY, "broken JSON");
  expect(readSavedSearches()).toEqual([]);
});

it("enforces the limit while allowing renaming and synchronizes other tabs", async () => {
  localStorage.setItem(SAVED_SEARCHES_KEY, JSON.stringify(Array.from({ length: 10 }, (_, i) => ({ name: `Grad ${i}`, path: `/?city=Grad${i}` }))));
  const user = userEvent.setup();
  render(<SavedSearches path="/?city=Beograd" />);
  await user.type(screen.getByLabelText("Naziv pretrage"), "Beograd");
  await user.click(screen.getByRole("button", { name: "Sačuvaj trenutnu pretragu" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Sačuvano je 10 pretraga");
  expect(readSavedSearches()).toHaveLength(10);
  localStorage.removeItem(SAVED_SEARCHES_KEY);
  act(() => window.dispatchEvent(new StorageEvent("storage", { key: SAVED_SEARCHES_KEY })));
  expect(screen.queryByRole("link", { name: "Grad 0" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Sačuvaj trenutnu pretragu" }));
  expect(screen.getByRole("link", { name: "Beograd" })).toBeVisible();
});

it("does not report success or discard the visible list when storage fails", async () => {
  localStorage.setItem(SAVED_SEARCHES_KEY, JSON.stringify([{ name: "Stan", path: "/?city=Beograd" }]));
  const user = userEvent.setup();
  render(<SavedSearches path="/" />);
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("Quota exceeded"); });
  await user.click(screen.getByRole("button", { name: "Ukloni pretragu: Stan" }));
  expect(screen.getByRole("alert")).toBeVisible();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Stan" })).toBeVisible();
});
