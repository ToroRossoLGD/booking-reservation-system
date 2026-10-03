import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import PropertyReportForm from "./PropertyReportForm";
import PropertyModerationPage from "./PropertyModerationPage";
import type { ModerationCase, PropertyReport } from "./moderation-types";

vi.mock("./api", () => ({ api: { me: vi.fn(), reportProperty: vi.fn(), propertyReports: vi.fn(), moderationCases: vi.fn(), moderateProperty: vi.fn(), moderationHistory: vi.fn() }, ApiError: class extends Error { constructor(message: string, public status: number) { super(message); } } }));
const listing: ModerationCase = { id: 7, title: "Stan pored reke", state: "clear", version: 0, note: "", appeal: "", is_published: true };
const report: PropertyReport = { id: 1, property_id: 7, category: "misleading", details: "Adresa i fotografije nisu tačne.", status: "pending", listing, created_at: "2026-10-03T08:00:00Z", resolved_at: null, snapshot: { title: listing.title, city: "Beograd", description: "Originalni opis oglasa.", offer_type: "sale", price_cents: 10000000, currency: "EUR" } };
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear(); localStorage.setItem("bookica_token", "member");
  vi.mocked(api.me).mockResolvedValue({ id: 4, email: "admin@example.com", role: "admin" });
  vi.mocked(api.propertyReports).mockResolvedValue({ items: [report], total: 1, has_next: false });
  vi.mocked(api.moderationCases).mockResolvedValue({ items: [], total: 0, has_next: false });
});

it("keeps the report request ID across an uncertain response and confirms submission", async () => {
  vi.mocked(api.reportProperty).mockRejectedValueOnce(new Error("network")).mockResolvedValueOnce(report);
  const user = userEvent.setup(); render(<PropertyReportForm propertyId={7} />);
  await user.click(screen.getByRole("button", { name: "Prijavi oglas" }));
  await user.type(screen.getByLabelText("Opis problema"), report.details);
  await user.click(screen.getByRole("button", { name: "Pošalji prijavu" }));
  await screen.findByRole("alert");
  await user.click(screen.getByRole("button", { name: "Pošalji prijavu" }));
  await screen.findByRole("status");
  const calls = vi.mocked(api.reportProperty).mock.calls;
  expect(calls[0]).toEqual(calls[1]);
  expect(calls[0][1]).toMatchObject({ category: "misleading", details: report.details });
});

it("requires an admin reason and blocks further decisions after a stale version", async () => {
  vi.mocked(api.moderateProperty).mockRejectedValue(new ApiError("stale", 409));
  const user = userEvent.setup(); render(<PropertyModerationPage />);
  await screen.findByRole("heading", { name: /Prijava #1/ });
  await user.selectOptions(screen.getByLabelText("Radnja"), "hide");
  expect(screen.getByRole("button", { name: "Suspenduj oglas" })).toBeDisabled();
  await user.type(screen.getByLabelText("Obrazloženje za vlasnika i administraciju"), "Ispravite podatke u opisu.");
  await user.click(screen.getByRole("button", { name: "Suspenduj oglas" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "Suspenduj oglas" })).toBeDisabled();
  expect(api.moderateProperty).toHaveBeenCalledWith(7, expect.objectContaining({ action: "hide", version: 0 }), 1);
});

it("shows only the reporter's history to customers without owner or admin controls", async () => {
  vi.mocked(api.me).mockResolvedValue({ id: 2, email: "guest@example.com", role: "customer" });
  render(<PropertyModerationPage />);
  await screen.findByRole("heading", { name: /Prijava #1/ });
  expect(api.propertyReports).toHaveBeenCalledWith(false, "pending", 0, expect.any(AbortSignal));
  expect(screen.queryByLabelText("Radnja")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Odluke o mojim oglasima" })).not.toBeInTheDocument();
});

it("allows the owner to appeal, without offering restoration or report details", async () => {
  vi.mocked(api.me).mockResolvedValue({ id: 1, email: "owner@example.com", role: "owner" });
  vi.mocked(api.propertyReports).mockResolvedValue({ items: [], total: 0, has_next: false });
  const suspended: ModerationCase = { ...listing, state: "suspended", version: 1, is_published: false, note: "Ispravite opis pre objavljivanja." };
  vi.mocked(api.moderationCases).mockResolvedValue({ items: [suspended], total: 1, has_next: false });
  vi.mocked(api.moderateProperty).mockResolvedValue({ ...suspended, state: "appealed", version: 2 });
  const user = userEvent.setup(); render(<PropertyModerationPage />);
  await user.click(await screen.findByRole("button", { name: "Odluke o mojim oglasima" }));
  await screen.findByText(/Obrazloženje administratora/);
  expect(screen.queryByRole("option", { name: "Ukini zabranu objavljivanja" })).not.toBeInTheDocument();
  expect(screen.queryByText(report.details)).not.toBeInTheDocument();
  await user.type(screen.getByLabelText("Obrazloženje za vlasnika i administraciju"), "Ispravio sam sve podatke.");
  await user.click(screen.getByRole("button", { name: "Zatraži ponovni pregled" }));
  await waitFor(() => expect(api.moderateProperty).toHaveBeenCalledWith(7, expect.objectContaining({ action: "appeal", version: 1 }), undefined));
});

it("clears private content when the active account token disappears", async () => {
  render(<PropertyModerationPage />);
  await screen.findByRole("heading", { name: /Prijava #1/ });
  localStorage.removeItem("bookica_token");
  window.dispatchEvent(new Event("storage"));
  await screen.findByRole("link", { name: "Prijavi se" });
  expect(screen.queryByText(report.details)).not.toBeInTheDocument();
});
