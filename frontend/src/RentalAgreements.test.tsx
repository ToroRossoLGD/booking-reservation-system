import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api } from "./api";
import RentalAgreements from "./RentalAgreements";
import type { RentalInquiry } from "./rental-types";
import type { RentalAgreement, RentalCharge } from "./rental-agreement-types";

vi.mock("./api", () => ({ api: { rentalAgreements: vi.fn(), proposeRentalAgreement: vi.fn(), decideRentalAgreement: vi.fn(), rentalCharges: vi.fn(), recordRentalPayment: vi.fn(), rentalChargeEvents: vi.fn() } }));
const inquiry: RentalInquiry = { id: 7, property_id: 1, title: "Stan", monthly_price_cents: 60000, currency: "EUR", move_in: "2030-01-31", duration_months: 3, message: "Najam", owner_reply: "", viewing_at: null, status: "open", version: 1, created_at: "2029-12-01T00:00:00Z" };
const agreement: RentalAgreement = { id: 9, inquiry_id: 7, title: "Stan", currency: "EUR", timezone: "Europe/Belgrade", start_date: "2030-01-31", end_date: "2030-04-30", months: 3, monthly_cents: 60000, deposit_cents: 0, notes: "Uslovi", status: "proposed", version: 1, created_at: "2029-12-01T00:00:00Z", accepted_at: null };
const charge: RentalCharge = { id: 11, sequence: 1, due_date: "2030-01-31", amount_cents: 60000, paid: false, version: 1, updated_at: null };
beforeEach(() => {
  vi.resetAllMocks(); localStorage.setItem("bookica_token", "owner");
  vi.mocked(api.rentalAgreements).mockResolvedValue([agreement]);
  vi.mocked(api.rentalCharges).mockResolvedValue([charge]);
  vi.mocked(api.rentalChargeEvents).mockResolvedValue([]);
});

it("loads privately on demand and requires tenant confirmation before acceptance", async () => {
  const user = userEvent.setup(); render(<RentalAgreements inquiry={inquiry} owner={false} />);
  expect(api.rentalAgreements).not.toHaveBeenCalled();
  await user.click(screen.getByText("Dogovor o najmu i kirije"));
  await user.click(await screen.findByText("Prihvati uslove najma"));
  expect(api.decideRentalAgreement).not.toHaveBeenCalled();
  expect(screen.getByText("Odustani od odluke")).toHaveFocus();
  vi.mocked(api.decideRentalAgreement).mockResolvedValue({ ...agreement, status: "accepted", version: 2 });
  vi.mocked(api.rentalAgreements).mockResolvedValue([{ ...agreement, status: "accepted", version: 2 }]);
  await user.click(screen.getByText("Potvrdi odluku o najmu"));
  await screen.findByText("Raspored kirija i depozita");
  expect(api.decideRentalAgreement).toHaveBeenCalledWith(9, 1, "accept");
  await user.click(screen.getByText("Raspored kirija i depozita"));
  await screen.findByText(/Dospeće:/);
  expect(screen.queryByText(/Evidentiraj uplatu/)).not.toBeInTheDocument();
});

it("submits owner terms with integer cents and a request identifier", async () => {
  vi.mocked(api.rentalAgreements).mockResolvedValue([]);
  vi.mocked(api.proposeRentalAgreement).mockResolvedValue(agreement);
  const user = userEvent.setup(); render(<RentalAgreements inquiry={inquiry} owner />);
  await user.click(screen.getByText("Dogovor o najmu i kirije"));
  const rent = await screen.findByLabelText("Mesečna kirija");
  await user.clear(rent); await user.type(rent, "650,25");
  await user.click(screen.getByText("Pošalji predlog najma"));
  await waitFor(() => expect(api.proposeRentalAgreement).toHaveBeenCalledWith(7, expect.objectContaining({ request_id: expect.any(String), start_date: "2030-01-31", months: 3, monthly_cents: 65025, deposit_cents: 0 })));
});

it("requires refresh after a conflicting decision and clears private data on account switch", async () => {
  vi.mocked(api.decideRentalAgreement).mockRejectedValue(new Error("conflict"));
  const user = userEvent.setup(); render(<RentalAgreements inquiry={inquiry} owner={false} />);
  await user.click(screen.getByText("Dogovor o najmu i kirije"));
  await user.click(await screen.findByText("Prihvati uslove najma"));
  await user.click(screen.getByText("Potvrdi odluku o najmu"));
  await screen.findByRole("alert");
  expect(screen.queryByText("Potvrdi odluku o najmu")).not.toBeInTheDocument();
  expect(screen.getByText("Prihvati uslove najma")).toBeDisabled();
  await user.click(screen.getByText("Osveži dogovore"));
  expect(await screen.findByText("Prihvati uslove najma")).toBeEnabled();
  act(() => { localStorage.setItem("bookica_token", "other"); window.dispatchEvent(new Event("storage")); });
  expect(screen.queryByText("Uslovi")).not.toBeInTheDocument();
});

it("confirms manual payments, exposes audit history and refreshes after stale updates", async () => {
  vi.mocked(api.rentalAgreements).mockResolvedValue([{ ...agreement, status: "accepted" }]);
  vi.mocked(api.recordRentalPayment).mockResolvedValue({ ...charge, paid: true, version: 2 });
  vi.mocked(api.rentalChargeEvents).mockResolvedValue([{ id: 1, paid: true, version: 2, created_at: "2030-01-31T12:00:00Z" }]);
  const user = userEvent.setup(); render(<RentalAgreements inquiry={inquiry} owner />);
  await user.click(screen.getByText("Dogovor o najmu i kirije"));
  await user.click(await screen.findByText("Raspored kirija i depozita"));
  await user.click(await screen.findByText(/Evidentiraj uplatu/));
  expect(api.recordRentalPayment).not.toHaveBeenCalled();
  await user.click(screen.getByText("Potvrdi evidenciju"));
  await screen.findByText(/Vlasnik je evidentirao uplatu/);
  expect(api.recordRentalPayment).toHaveBeenCalledWith(9, 11, 1, true);
  await user.click(screen.getByText("Istorija evidencije"));
  await screen.findByText(/Uplata evidentirana/);
  vi.mocked(api.recordRentalPayment).mockRejectedValue(new Error("stale"));
  await user.click(screen.getByText(/Ispravi oznaku uplate/));
  await user.click(screen.getByText("Potvrdi evidenciju"));
  await screen.findByRole("alert");
  expect(screen.queryByText("Potvrdi evidenciju")).not.toBeInTheDocument();
  expect(screen.getByText(/Ispravi oznaku uplate/)).toBeDisabled();
});
