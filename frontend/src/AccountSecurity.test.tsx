import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import AccountSecurity from "./AccountSecurity";

vi.mock("./api", async importOriginal => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, api: { me: vi.fn(), logoutAllSessions: vi.fn() } };
});
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear();
  localStorage.setItem("bookica_token", "session");
  vi.mocked(api.me).mockResolvedValue({ id: 1, email: "guest@example.com", role: "customer", email_verified: false });
});

async function confirm() {
  await userEvent.click(await screen.findByRole("button", { name: "Odjavi sve uređaje" }));
  await userEvent.click(screen.getByRole("button", { name: "Potvrdi odjavu svuda" }));
}

it("requires confirmation, allows cancel, and clears local credentials after success", async () => {
  vi.mocked(api.logoutAllSessions).mockResolvedValue(undefined);
  render(<AccountSecurity />);
  await userEvent.click(await screen.findByRole("button", { name: "Odjavi sve uređaje" }));
  await userEvent.click(screen.getByRole("button", { name: "Odustani" }));
  expect(api.logoutAllSessions).not.toHaveBeenCalled();
  expect(localStorage.getItem("bookica_token")).toBe("session");
  await confirm();
  expect(await screen.findByRole("status")).toHaveTextContent("Sve sesije i API ključevi su poništeni");
  expect(localStorage.getItem("bookica_token")).toBeNull();
});

it("preserves the local session after failure and permits retry", async () => {
  vi.mocked(api.logoutAllSessions).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(undefined);
  render(<AccountSecurity />); await confirm();
  expect(await screen.findByRole("alert")).toHaveTextContent("nije potvrđena");
  expect(localStorage.getItem("bookica_token")).toBe("session");
  await userEvent.click(screen.getByRole("button", { name: "Potvrdi odjavu svuda" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Sve sesije");
  expect(api.logoutAllSessions).toHaveBeenCalledTimes(2);
});

it("does not claim global revocation when authentication has expired", async () => {
  vi.mocked(api.logoutAllSessions).mockRejectedValue(new ApiError("expired", 401));
  render(<AccountSecurity />); await confirm();
  expect(await screen.findByRole("alert")).toHaveTextContent("odjava svih uređaja nije potvrđena");
  expect(localStorage.getItem("bookica_token")).toBeNull();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it("requires login before offering revocation", async () => {
  vi.mocked(api.me).mockRejectedValue(new ApiError("guest", 401));
  render(<AccountSecurity />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Prijavi se");
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it("disables confirmation while pending and retains credentials until completion", async () => {
  let complete!: () => void;
  vi.mocked(api.logoutAllSessions).mockReturnValue(new Promise<void>(resolve => { complete = resolve; }));
  render(<AccountSecurity />); await confirm();
  expect(screen.getByRole("button", { name: "Odjavljivanje…" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Odustani" })).toBeDisabled();
  expect(localStorage.getItem("bookica_token")).toBe("session");
  expect(api.logoutAllSessions).toHaveBeenCalledTimes(1);
  await act(async () => complete());
  expect(localStorage.getItem("bookica_token")).toBeNull();
});
