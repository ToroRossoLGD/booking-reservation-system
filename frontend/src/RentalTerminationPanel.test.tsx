import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api } from "./api";
import RentalTerminationPanel from "./RentalTerminationPanel";
import RentalPaymentPlan from "./RentalPaymentPlan";
import type { RentalAgreement, RentalCharge, RentalTermination } from "./rental-agreement-types";

vi.mock("./api", () => ({ api: { rentalTerminations: vi.fn(), proposeRentalTermination: vi.fn(), decideRentalTermination: vi.fn(), rentalCharges: vi.fn(), rentalChargeEvents: vi.fn() } }));
const agreement: RentalAgreement = { id: 1, inquiry_id: 1, title: "Stan", currency: "EUR", timezone: "Europe/Belgrade", start_date: "2030-01-31", end_date: "2030-04-30", months: 3, monthly_cents: 60000, deposit_cents: 60000, notes: "", status: "accepted", version: 2, created_at: "2029-12-01T00:00:00Z", accepted_at: "2029-12-02T00:00:00Z" };
const charges: RentalCharge[] = [0, 1, 2, 3].map(sequence => ({ id: sequence + 1, sequence, due_date: sequence < 2 ? "2030-01-31" : sequence === 2 ? "2030-02-28" : "2030-03-31", amount_cents: 60000, paid: false, version: 1, updated_at: null }));
const termination: RentalTermination = { id: 5, end_date: "2030-02-28", notes: "Selidba", status: "proposed", version: 1, created_at: "2029-12-03T00:00:00Z", decided_at: null };
beforeEach(() => {
  vi.resetAllMocks(); localStorage.setItem("bookica_token", "owner");
  vi.mocked(api.rentalTerminations).mockResolvedValue([]);
  vi.mocked(api.rentalCharges).mockResolvedValue(charges);
});

it("previews owner proposal and preserves request ID after an uncertain write and refresh", async () => {
  const user = userEvent.setup();
  vi.mocked(api.proposeRentalTermination).mockRejectedValueOnce(new Error("offline")).mockResolvedValue(termination);
  render(<RentalTerminationPanel agreement={agreement} owner token="owner" onAccepted={vi.fn()} />);
  expect(api.rentalTerminations).not.toHaveBeenCalled();
  await user.click(screen.getByText("Prevremeni završetak najma"));
  await user.selectOptions(await screen.findByLabelText("Novi datum završetka"), "2030-02-28");
  await user.type(screen.getByLabelText("Razlog i dogovorene napomene"), "Selidba");
  await user.click(screen.getByText("Pregledaj predlog završetka"));
  expect(api.proposeRentalTermination).not.toHaveBeenCalled();
  expect(screen.getByText("Odustani od ove odluke")).toHaveFocus();
  expect(screen.getAllByText(/ukida se 2 stavki/).length).toBeGreaterThan(0);
  await user.click(screen.getByText("Potvrdi odluku o završetku"));
  await screen.findByRole("alert");
  expect(screen.getByText("Pregledaj predlog završetka")).toBeDisabled();
  await user.click(screen.getByText("Osveži završetak najma"));
  await user.click(await screen.findByText("Pregledaj predlog završetka"));
  await user.click(screen.getByText("Potvrdi odluku o završetku"));
  await waitFor(() => expect(api.proposeRentalTermination).toHaveBeenCalledTimes(2));
  expect(vi.mocked(api.proposeRentalTermination).mock.calls[0]).toEqual(vi.mocked(api.proposeRentalTermination).mock.calls[1]);
  expect(api.proposeRentalTermination).toHaveBeenLastCalledWith(1, expect.objectContaining({ version: 2, end_date: "2030-02-28", notes: "Selidba" }));
});

it("requires tenant confirmation and reloads the agreement after acceptance", async () => {
  vi.mocked(api.rentalTerminations).mockResolvedValue([termination]);
  vi.mocked(api.decideRentalTermination).mockResolvedValue({ ...termination, status: "accepted" });
  const user = userEvent.setup(); const reload = vi.fn();
  render(<RentalTerminationPanel agreement={agreement} owner={false} token="owner" onAccepted={reload} />);
  await user.click(screen.getByText("Prevremeni završetak najma"));
  await user.click(await screen.findByText("Prihvati raniji završetak"));
  expect(api.decideRentalTermination).not.toHaveBeenCalled();
  expect(screen.queryByLabelText("Novi datum završetka")).not.toBeInTheDocument();
  await user.click(screen.getByText("Potvrdi odluku o završetku"));
  await waitFor(() => expect(reload).toHaveBeenCalledOnce());
  expect(api.decideRentalTermination).toHaveBeenCalledWith(1, 5, 1, "accept");
});

it("prevents sending a decision after the account changes and rejects conflict retries until refresh", async () => {
  vi.mocked(api.rentalTerminations).mockResolvedValue([termination]);
  vi.mocked(api.decideRentalTermination).mockRejectedValue(new Error("conflict"));
  const user = userEvent.setup();
  render(<RentalTerminationPanel agreement={agreement} owner={false} token="owner" onAccepted={vi.fn()} />);
  await user.click(screen.getByText("Prevremeni završetak najma"));
  await user.click(await screen.findByText("Prihvati raniji završetak"));
  localStorage.setItem("bookica_token", "other");
  await user.click(screen.getByText("Potvrdi odluku o završetku"));
  expect(api.decideRentalTermination).not.toHaveBeenCalled();
  localStorage.setItem("bookica_token", "owner");
  await user.click(screen.getByText("Potvrdi odluku o završetku"));
  await screen.findByRole("alert");
  expect(screen.queryByText("Potvrdi odluku o završetku")).not.toBeInTheDocument();
  expect(screen.getByText("Prihvati raniji završetak")).toBeDisabled();
});

it("excludes dates that would void paid rent and keeps voided charges out of the balance", async () => {
  const user = userEvent.setup();
  vi.mocked(api.rentalCharges).mockResolvedValue(charges.map(c => ({ ...c, paid: c.sequence === 3 })));
  const { unmount } = render(<RentalTerminationPanel agreement={agreement} owner token="owner" onAccepted={vi.fn()} />);
  await user.click(screen.getByText("Prevremeni završetak najma"));
  await screen.findByText(/Nema dostupnog mesečnog datuma/);
  expect(screen.queryByLabelText("Novi datum završetka")).not.toBeInTheDocument();
  unmount();
  vi.mocked(api.rentalCharges).mockResolvedValue(charges.map(c => ({ ...c, voided_at: c.sequence > 1 ? "2029-12-04T00:00:00Z" : null })));
  render(<RentalPaymentPlan agreement={{ ...agreement, terminated_on: "2030-02-28" }} owner token="owner" />);
  await user.click(screen.getByText("Raspored kirija i depozita"));
  await screen.findAllByText(/Ukinuta kirija/);
  expect(screen.getAllByRole("button", { name: /Evidentiraj uplatu/ })).toHaveLength(2);
  expect(screen.getByText(/Bez evidentirane uplate/).textContent).toMatch(/1[.\s]200/);
});
