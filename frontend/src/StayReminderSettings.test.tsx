import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import StayReminderSettings from "./StayReminderSettings";

vi.mock("./api", () => ({ api: { stayReminderPreferences: vi.fn(), setStayReminderPreferences: vi.fn(), viewingReminderPreferences: vi.fn(), setViewingReminderPreferences: vi.fn() } }));
afterEach(() => { vi.resetAllMocks(); localStorage.clear(); });

it("keeps viewing preferences separate from stay preferences", async () => {
  vi.mocked(api.viewingReminderPreferences).mockResolvedValue({ enabled: true });
  vi.mocked(api.setViewingReminderPreferences).mockResolvedValue({ enabled: false });
  render(<StayReminderSettings viewing />);
  fireEvent.click(screen.getByRole("button", { name: "Podsetnici za razgledanja" }));
  fireEvent.click(await screen.findByText("Isključi podsetnike"));
  expect(await screen.findByText("Podsetnici su isključeni.")).toBeVisible();
  expect(api.setViewingReminderPreferences).toHaveBeenCalledWith(false);
  expect(api.stayReminderPreferences).not.toHaveBeenCalled();
  expect(api.setStayReminderPreferences).not.toHaveBeenCalled();
});

it("loads only on demand and saves the personal preference", async () => {
  vi.mocked(api.stayReminderPreferences).mockResolvedValue({ enabled: true });
  vi.mocked(api.setStayReminderPreferences).mockResolvedValue({ enabled: false });
  render(<StayReminderSettings />);
  expect(api.stayReminderPreferences).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Podsetnici za dolazak i odlazak"));
  fireEvent.click(await screen.findByText("Isključi podsetnike"));
  expect(await screen.findByText("Podsetnici su isključeni.")).toBeVisible();
  expect(api.setStayReminderPreferences).toHaveBeenCalledWith(false);
});

it("requires refreshing after an uncertain save and supports read retry", async () => {
  vi.mocked(api.stayReminderPreferences).mockRejectedValueOnce(new Error()).mockResolvedValue({ enabled: true });
  vi.mocked(api.setStayReminderPreferences).mockRejectedValue(new Error());
  render(<StayReminderSettings />);
  fireEvent.click(screen.getByText("Podsetnici za dolazak i odlazak"));
  fireEvent.click(await screen.findByText("Osveži podešavanje"));
  fireEvent.click(await screen.findByText("Isključi podsetnike"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Promena nije potvrđena");
  expect(screen.getByText("Isključi podsetnike")).toBeDisabled();
});

it("drops old account responses and aborts its read", async () => {
  localStorage.setItem("bookica_token", "first");
  let resolve!: (value: { enabled: boolean }) => void;
  vi.mocked(api.stayReminderPreferences).mockImplementation(() => new Promise(done => { resolve = done; }));
  render(<StayReminderSettings />);
  fireEvent.click(screen.getByText("Podsetnici za dolazak i odlazak"));
  const signal = vi.mocked(api.stayReminderPreferences).mock.calls[0][0];
  localStorage.setItem("bookica_token", "second");
  await act(async () => { window.dispatchEvent(new Event("storage")); resolve({ enabled: true }); });
  expect(signal?.aborted).toBe(true);
  expect(screen.queryByText("Isključi podsetnike")).toBeNull();
});
