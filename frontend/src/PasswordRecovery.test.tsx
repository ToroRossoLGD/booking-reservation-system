import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import { ForgotPasswordPage, ResetPasswordPage } from "./PasswordRecovery";
import { takePasswordResetToken } from "./passwordResetToken";

vi.mock("./api", async importOriginal => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, api: { requestPasswordReset: vi.fn(), confirmPasswordReset: vi.fn() } };
});
beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); });

it("shows generic confirmation without displaying whether the address exists", async () => {
  vi.mocked(api.requestPasswordReset).mockResolvedValue({ message: "generic" });
  render(<MemoryRouter><ForgotPasswordPage /></MemoryRouter>);
  await userEvent.type(screen.getByLabelText("Email adresa"), "user@example.com");
  await userEvent.click(screen.getByRole("button", { name: "Pošalji link" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Ako postoji nalog");
  expect(api.requestPasswordReset).toHaveBeenCalledWith("user@example.com");
});

it("requires matching passwords, then clears the old local session on success", async () => {
  vi.mocked(api.confirmPasswordReset).mockResolvedValue({ message: "ok" });
  localStorage.setItem("bookica_token", "old-session");
  render(<MemoryRouter><ResetPasswordPage token={"a".repeat(43)} /></MemoryRouter>);
  fireEvent.change(screen.getByLabelText("Nova lozinka"), { target: { value: "new-password-42" } });
  fireEvent.change(screen.getByLabelText("Ponovite lozinku"), { target: { value: "wrong-password" } });
  await userEvent.click(screen.getByRole("button", { name: "Sačuvaj lozinku" }));
  expect(screen.getByRole("alert")).toHaveTextContent("ne poklapaju");
  expect(api.confirmPasswordReset).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Ponovite lozinku"), { target: { value: "new-password-42" } });
  await userEvent.click(screen.getByRole("button", { name: "Sačuvaj lozinku" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Lozinka je promenjena");
  expect(localStorage.getItem("bookica_token")).toBeNull();
  expect(screen.queryByLabelText("Nova lozinka")).not.toBeInTheDocument();
});

it.each([400, 409, 410])("offers a new link after rejected token (%s)", async status => {
  vi.mocked(api.confirmPasswordReset).mockRejectedValue(new ApiError("internal", status));
  render(<MemoryRouter><ResetPasswordPage token={"a".repeat(43)} /></MemoryRouter>);
  for (const name of ["Nova lozinka", "Ponovite lozinku"]) fireEvent.change(screen.getByLabelText(name), { target: { value: "new-password-42" } });
  await userEvent.click(screen.getByRole("button", { name: "Sačuvaj lozinku" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Zatražite novi link");
  expect(screen.getByRole("link", { name: "Zatraži novi link" })).toHaveAttribute("href", "/forgot-password");
});

it("does not submit when the link has no token", () => {
  render(<MemoryRouter><ResetPasswordPage token="" /></MemoryRouter>);
  expect(screen.getByRole("alert")).toHaveTextContent("Link nedostaje");
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it("takes the fragment token out of the URL and never stores it", () => {
  const token = "a".repeat(43);
  window.history.replaceState(null, "", `/reset-password#token=${token}`);
  expect(takePasswordResetToken()).toBe(token);
  expect(window.location.hash).toBe("");
  expect(localStorage.length).toBe(0);
  expect(takePasswordResetToken()).toBe("");
  window.history.replaceState(null, "", "/");
});
