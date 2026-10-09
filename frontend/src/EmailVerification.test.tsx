import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import EmailVerification from "./EmailVerification";
import { getEmailVerificationToken, subscribeEmailVerificationToken, syncEmailVerificationToken, takeEmailVerificationToken } from "./emailVerificationToken";

vi.mock("./api", async importOriginal => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, api: { me: vi.fn(), requestEmailVerification: vi.fn(), confirmEmailVerification: vi.fn() } };
});
beforeEach(() => { vi.resetAllMocks(); localStorage.clear(); });

it("requires a deliberate click and confirms without a login", async () => {
  vi.mocked(api.confirmEmailVerification).mockResolvedValue({ message: "ok" });
  render(<MemoryRouter><EmailVerification token={"a".repeat(43)} /></MemoryRouter>);
  expect(api.confirmEmailVerification).not.toHaveBeenCalled();
  expect(api.me).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Potvrdi email" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Email adresa je potvrđena");
  expect(api.confirmEmailVerification).toHaveBeenCalledWith("a".repeat(43));
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it.each([400, 409, 410])("offers resend for a rejected link (%s)", async status => {
  vi.mocked(api.confirmEmailVerification).mockRejectedValue(new ApiError("internal", status));
  render(<MemoryRouter><EmailVerification token={"a".repeat(43)} /></MemoryRouter>);
  await userEvent.click(screen.getByRole("button", { name: "Potvrdi email" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Zatražite novi link");
  expect(screen.getByRole("link", { name: "Zatraži novi link" })).toHaveAttribute("href", "/verify-email");
});

it("resends only to the authenticated account and prevents immediate repeated clicks", async () => {
  vi.mocked(api.me).mockResolvedValue({ id: 5, email: "user@example.com", role: "customer", email_verified: false });
  vi.mocked(api.requestEmailVerification).mockResolvedValue({ message: "generic" });
  render(<MemoryRouter><EmailVerification token="" /></MemoryRouter>);
  await userEvent.click(await screen.findByRole("button", { name: "Pošalji novi link" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Proverite i spam folder");
  expect(api.requestEmailVerification).toHaveBeenCalledWith();
  expect(screen.getByRole("button")).toBeDisabled();
});

it("asks guests to log in and does not send automatically", async () => {
  vi.mocked(api.me).mockRejectedValue(new ApiError("unauthorized", 401));
  render(<MemoryRouter><EmailVerification token="" /></MemoryRouter>);
  expect(await screen.findByText(/Prijavite se da zatražite/)).toBeVisible();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  expect(api.requestEmailVerification).not.toHaveBeenCalled();
});

it("shows the server wait after rate limiting instead of calling the link invalid", async () => {
  vi.mocked(api.confirmEmailVerification).mockRejectedValue(new ApiError("Too many", 429, 20));
  render(<MemoryRouter><EmailVerification token={"a".repeat(43)} /></MemoryRouter>);
  await userEvent.click(screen.getByRole("button", { name: "Potvrdi email" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Sačekajte 20 sekundi");
  expect(api.confirmEmailVerification).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button", { name: "Potvrdi email" })).toBeEnabled();
});

it("removes fragment secrets without storing them", () => {
  const token = "a".repeat(43);
  window.history.replaceState(null, "", `/verify-email#token=${token}`);
  expect(takeEmailVerificationToken()).toBe(token);
  expect(window.location.hash).toBe("");
  expect(localStorage.length).toBe(0);
  expect(takeEmailVerificationToken()).toBe("");
  window.history.replaceState(null, "", "/");
});

it("captures later fragment navigation and clears the token when leaving", () => {
  window.history.replaceState(null, "", "/verify-email");
  const changed = vi.fn();
  const unsubscribe = subscribeEmailVerificationToken(changed);
  try {
    for (const token of ["a".repeat(43), "b".repeat(43)]) {
      window.history.replaceState({ key: "router-state" }, "", `/verify-email#token=${token}`);
      window.dispatchEvent(new HashChangeEvent("hashchange"));
      expect(getEmailVerificationToken()).toBe(token);
      expect(window.location.hash).toBe("");
      expect(window.history.state).toEqual({ key: "router-state" });
    }
    expect(changed).toHaveBeenCalledTimes(2);
    window.history.replaceState(null, "", "/account");
    syncEmailVerificationToken();
    expect(getEmailVerificationToken()).toBe("");
    expect(localStorage.length).toBe(0);
  } finally {
    unsubscribe();
    window.history.replaceState(null, "", "/");
  }
});
