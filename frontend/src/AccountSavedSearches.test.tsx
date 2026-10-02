import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import AccountSavedSearches from "./AccountSavedSearches";
import { api } from "./api";

vi.mock("./api", () => ({ api: { accountSearches: vi.fn(), saveAccountSearch: vi.fn(), removeAccountSearch: vi.fn(), setSearchAlerts: vi.fn() }, ApiError: class extends Error { status = 409; } }));
beforeEach(() => { vi.resetAllMocks(); localStorage.setItem("bookica_token", "account-one"); vi.mocked(api.accountSearches).mockResolvedValue([]); });
afterEach(() => localStorage.clear());

it("requires explicit alert opt-in and keeps the saved state after a failed toggle", async () => {
  const item = { id: 1, name: "Stan", path: "/", alerts_enabled: false };
  vi.mocked(api.accountSearches).mockResolvedValue([item]);
  vi.mocked(api.setSearchAlerts).mockResolvedValueOnce({ ...item, alerts_enabled: true }).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(item);
  const user = userEvent.setup();
  render(<AccountSavedSearches path="/" localItems={[]} />);
  await user.click(screen.getByRole("button", { name: "Pretrage na nalogu" }));
  const enable = await screen.findByRole("button", { name: "Uključi obaveštenja: Stan" });
  expect(api.setSearchAlerts).not.toHaveBeenCalled();
  expect(enable).toHaveAttribute("aria-pressed", "false");
  await user.click(enable);
  expect(api.setSearchAlerts).toHaveBeenCalledWith(1, true);
  await user.click(await screen.findByRole("button", { name: "Isključi obaveštenja: Stan" }));
  expect(await screen.findByRole("alert")).toBeVisible();
  expect(screen.getByRole("button", { name: "Isključi obaveštenja: Stan" })).toHaveAttribute("aria-pressed", "true");
  await user.click(screen.getByRole("button", { name: "Isključi obaveštenja: Stan" }));
  expect(await screen.findByRole("button", { name: "Uključi obaveštenja: Stan" })).toBeVisible();
});

it("loads on demand and only transfers a local search after an explicit click", async () => {
  const user = userEvent.setup();
  const local = { name: "Moj stan", path: "/?city=Beograd" };
  vi.mocked(api.saveAccountSearch).mockResolvedValue({ ...local, id: 4 });
  render(<AccountSavedSearches path="/" localItems={[local]} />);
  expect(api.accountSearches).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Pretrage na nalogu" }));
  await screen.findByText("Još nema pretraga na nalogu.");
  expect(api.saveAccountSearch).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Sačuvaj na nalogu: Moj stan" }));
  await waitFor(() => expect(api.saveAccountSearch).toHaveBeenCalledWith(local));
  expect(await screen.findByRole("link", { name: "Moj stan" })).toHaveAttribute("href", local.path);
  expect(screen.getByRole("button", { name: "Sačuvaj na nalogu: Moj stan" })).toBeDisabled();
  expect(local.name).toBe("Moj stan");
});

it("saves current filters, renames matching searches and preserves list on failed removal", async () => {
  const user = userEvent.setup();
  const saved = { id: 1, name: "Old", path: "/?city=Novi+Sad&rooms=0" };
  vi.mocked(api.accountSearches).mockResolvedValue([saved]);
  vi.mocked(api.saveAccountSearch).mockResolvedValue({ ...saved, name: "New" });
  vi.mocked(api.removeAccountSearch).mockRejectedValue(new Error("offline"));
  render(<AccountSavedSearches path="/?rooms=0&city=Novi+Sad&offset=12" localItems={[]} />);
  await user.click(screen.getByRole("button", { name: "Pretrage na nalogu" }));
  await screen.findByRole("link", { name: "Old" });
  await user.type(screen.getByLabelText("Naziv pretrage na nalogu"), "New");
  await user.click(screen.getByRole("button", { name: "Promeni naziv na nalogu" }));
  expect(await screen.findByRole("link", { name: "New" })).toBeVisible();
  expect(api.saveAccountSearch).toHaveBeenCalledWith({ name: "New", path: saved.path });
  await user.click(screen.getByRole("button", { name: "Ukloni sa naloga: New" }));
  expect(await screen.findByRole("alert")).toBeVisible();
  expect(screen.getByRole("link", { name: "New" })).toBeVisible();
});

it("clears private state and ignores late responses after switching accounts", async () => {
  let resolve!: (items: { id: number; name: string; path: string }[]) => void;
  vi.mocked(api.accountSearches).mockReturnValueOnce(new Promise(done => { resolve = done; }));
  const user = userEvent.setup();
  render(<AccountSavedSearches path="/" localItems={[]} />);
  await user.click(screen.getByRole("button", { name: "Pretrage na nalogu" }));
  act(() => { localStorage.setItem("bookica_token", "account-two"); window.dispatchEvent(new StorageEvent("storage", { key: "bookica_token" })); });
  await act(async () => resolve([{ id: 1, name: "Private old search", path: "/" }]));
  expect(screen.queryByText("Private old search")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Pretrage na nalogu" }));
  expect(await screen.findByText("Još nema pretraga na nalogu.")).toBeVisible();
  act(() => { localStorage.removeItem("bookica_token"); window.dispatchEvent(new StorageEvent("storage", { key: "bookica_token" })); });
  expect(screen.queryByRole("region", { name: "Pretrage na nalogu" })).not.toBeInTheDocument();
  expect(within(screen.getByText(/da sačuvaš pretrage na nalogu/)).getByRole("link")).toHaveAttribute("href", "/account");
});
