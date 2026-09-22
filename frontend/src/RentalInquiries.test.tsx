import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import RentalInquiryForm from "./RentalInquiryForm";
import RentalInquiriesPage from "./RentalInquiriesPage";
import type { RentalInquiry } from "./rental-types";

vi.mock("./api", () => ({ api: { createRentalInquiry: vi.fn(), rentalInquiries: vi.fn(), updateRentalInquiry: vi.fn() }, ApiError: class extends Error { status: number; constructor(message: string, status: number) { super(message); this.status = status; } } }));
const property = { id: 1, venue_id: 1, title: "Stan za najam", description: "Udoban stan u centru grada.", city: "Beograd", offer_type: "long_term" as const, area_sqm: 50, rooms: 2, price_cents: 60000, currency: "EUR" as const, contact_email: "owner@example.com", is_published: true };
const inquiry: RentalInquiry = { id: 1, property_id: 1, title: property.title, monthly_price_cents: 60000, currency: "EUR", move_in: "2030-10-01", duration_months: 12, message: "Želim da pogledam stan.", owner_reply: "Vidimo se ispred ulaza.", viewing_at: "2030-09-25T12:00:00Z", status: "viewing_proposed", version: 2, created_at: "2030-09-01T12:00:00Z" };
beforeEach(() => { vi.resetAllMocks(); vi.mocked(api.rentalInquiries).mockResolvedValue({ items: [inquiry], total: 1, has_next: false }); vi.mocked(api.updateRentalInquiry).mockResolvedValue(inquiry); });

it("keeps the same request identifier after a failed submission", async () => {
  vi.mocked(api.createRentalInquiry).mockRejectedValueOnce(new Error("offline")).mockResolvedValue(inquiry);
  const user = userEvent.setup();
  render(<RentalInquiryForm property={property} />);
  fireEvent.change(screen.getByLabelText("Željeno useljenje"), { target: { value: "2030-10-01" } });
  await user.type(screen.getByLabelText("Poruka vlasniku"), inquiry.message);
  await user.click(screen.getByRole("button", { name: "Pošalji upit za najam" }));
  await screen.findByRole("alert");
  await user.click(screen.getByRole("button", { name: "Pošalji upit za najam" }));
  await screen.findByText("Upit je poslat vlasniku");
  expect(api.createRentalInquiry).toHaveBeenCalledTimes(2);
  expect(vi.mocked(api.createRentalInquiry).mock.calls[0]).toEqual(vi.mocked(api.createRentalInquiry).mock.calls[1]);
  expect(vi.mocked(api.createRentalInquiry).mock.calls[0][1]).toMatchObject({ move_in: "2030-10-01", duration_months: 12, message: inquiry.message });
});

it("lets a tenant confirm the displayed version of a viewing", async () => {
  const user = userEvent.setup();
  render(<RentalInquiriesPage />);
  await user.click(await screen.findByRole("button", { name: "Prihvati termin" }));
  await waitFor(() => expect(api.updateRentalInquiry).toHaveBeenCalledWith(1, { action: "confirm", version: 2 }));
  expect(screen.queryByLabelText("Odgovor zakupcu")).not.toBeInTheDocument();
});

it("lets an owner propose a viewing with an explicit timezone", async () => {
  const user = userEvent.setup();
  render(<RentalInquiriesPage owner />);
  fireEvent.change(await screen.findByLabelText("Predloži termin razgledanja (opciono)"), { target: { value: "2030-09-26T14:00" } });
  await user.click(screen.getByRole("button", { name: "Pošalji predlog termina" }));
  await waitFor(() => expect(api.updateRentalInquiry).toHaveBeenCalledWith(1, { action: "propose", version: 2, owner_reply: inquiry.owner_reply, viewing_at: new Date("2030-09-26T14:00").toISOString() }));
  expect(api.rentalInquiries).toHaveBeenCalledWith(true, 0);
});

it("reports stale changes and permits refreshing", async () => {
  vi.mocked(api.updateRentalInquiry).mockRejectedValue(new ApiError("Stale", 409));
  const user = userEvent.setup();
  render(<RentalInquiriesPage />);
  await user.click(await screen.findByRole("button", { name: "Prihvati termin" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Upit je izmenjen");
  await user.click(screen.getByRole("button", { name: "Osveži upite" }));
  await waitFor(() => expect(api.rentalInquiries).toHaveBeenCalledTimes(2));
});

it("requires confirmation to withdraw and hides actions for closed inquiries", async () => {
  const user = userEvent.setup();
  vi.mocked(api.rentalInquiries).mockResolvedValueOnce({ items: [inquiry], total: 1, has_next: false }).mockResolvedValue({ items: [{ ...inquiry, status: "withdrawn", version: 3 }], total: 1, has_next: false });
  render(<RentalInquiriesPage />);
  await user.click(await screen.findByRole("button", { name: "Povuci upit" }));
  expect(api.updateRentalInquiry).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Potvrdi" }));
  await screen.findByText("Povučen upit");
  expect(api.updateRentalInquiry).toHaveBeenCalledWith(1, { action: "withdraw", version: 2 });
  expect(screen.queryByRole("button", { name: "Prihvati termin" })).not.toBeInTheDocument();
});
