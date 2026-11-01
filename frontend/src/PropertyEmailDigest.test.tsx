import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import PropertyEmailDigest, { type EmailDigestStatus } from "./PropertyEmailDigest";

vi.mock("./api", () => ({ api: { emailDigestStatus: vi.fn(), setEmailDigest: vi.fn() } }));
afterEach(() => { vi.resetAllMocks(); localStorage.clear(); });
const status: EmailDigestStatus = { interval_hours: 1, next_run_at: null, enabled: false, verified: true, available: true, last_status: "unconfigured", last_attempt_at: null, last_accepted_at: null };

it("changes frequency without enabling email and shows the persisted schedule", async () => {
  vi.mocked(api.emailDigestStatus).mockResolvedValue(status);
  vi.mocked(api.setEmailDigest).mockResolvedValue({ ...status, interval_hours: 24 });
  render(<PropertyEmailDigest />);
  fireEvent.click(screen.getByRole("button", { name: "Email sažetak obaveštenja" }));
  fireEvent.change(await screen.findByLabelText("Učestalost email sažetka"), { target: { value: "24" } });
  await screen.findByText("Email sažetak je isključen.");
  expect(vi.mocked(api.setEmailDigest)).toHaveBeenCalledWith(false, 24);
  expect(await screen.findByDisplayValue("Jednom dnevno")).toBeVisible();
});

it("requires explicit verified opt-in and supports disabling", async () => {
  vi.mocked(api.emailDigestStatus).mockResolvedValue(status);
  vi.mocked(api.setEmailDigest).mockResolvedValueOnce({ ...status, enabled: true }).mockResolvedValue(status);
  render(<PropertyEmailDigest />);
  expect(api.emailDigestStatus).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Email sažetak obaveštenja" }));
  expect(await screen.findByText("Email sažetak je isključen.")).toBeVisible();
  expect(api.setEmailDigest).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Uključi email sažetak"));
  fireEvent.click(await screen.findByText("Isključi email sažetak"));
  expect(await screen.findByText("Email sažetak je isključen.")).toBeVisible();
  expect(vi.mocked(api.setEmailDigest).mock.calls).toEqual([[true], [false]]);
});

it("blocks enabling without verified email and explains server availability", async () => {
  vi.mocked(api.emailDigestStatus).mockResolvedValue({ ...status, verified: false, available: false });
  render(<PropertyEmailDigest />);
  fireEvent.click(screen.getByRole("button", { name: "Email sažetak obaveštenja" }));
  expect(await screen.findByText("Uključi email sažetak")).toBeDisabled();
  expect(screen.getByText("verifikuj email adresu")).toHaveAttribute("href", "/verify-email");
  expect(screen.getByText("Email sažetak nije aktiviran na serveru.")).toBeVisible();
});

it("requires a status refresh after uncertain writes", async () => {
  vi.mocked(api.emailDigestStatus).mockResolvedValue(status);
  vi.mocked(api.setEmailDigest).mockRejectedValue(new Error());
  render(<PropertyEmailDigest />);
  fireEvent.click(screen.getByRole("button", { name: "Email sažetak obaveštenja" }));
  fireEvent.click(await screen.findByText("Uključi email sažetak"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Promena nije potvrđena");
  expect(screen.getByText("Uključi email sažetak")).toBeDisabled();
  fireEvent.click(screen.getByText("Osveži status email sažetka"));
  expect(await screen.findByText("Uključi email sažetak")).toBeEnabled();
});

it("discards previous-account reads", async () => {
  localStorage.setItem("bookica_token", "first");
  let resolve!: (value: EmailDigestStatus) => void;
  vi.mocked(api.emailDigestStatus).mockImplementation(() => new Promise(done => { resolve = done; }));
  render(<PropertyEmailDigest />);
  fireEvent.click(screen.getByRole("button", { name: "Email sažetak obaveštenja" }));
  const signal = vi.mocked(api.emailDigestStatus).mock.calls[0][0];
  localStorage.setItem("bookica_token", "second");
  await act(async () => { window.dispatchEvent(new Event("storage")); resolve(status); });
  expect(signal?.aborted).toBe(true);
  expect(screen.queryByText("Uključi email sažetak")).toBeNull();
});
