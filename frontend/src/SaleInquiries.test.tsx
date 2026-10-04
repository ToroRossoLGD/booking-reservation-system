import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api } from "./api";
import SaleInquiryForm from "./SaleInquiryForm";
import RentalInquiriesPage from "./RentalInquiriesPage";
import { viewingCalendar } from "./calendar-export";
import type { SaleInquiry } from "./rental-types";

vi.mock("./api", () => ({ api: { createSaleInquiry: vi.fn(), saleInquiries: vi.fn(), updateSaleInquiry: vi.fn() }, ApiError: class extends Error {} }));
const property = { id: 7, venue_id: 1, title: "Stan za prodaju", description: "Stan sa terasom u centru.", city: "Beograd", offer_type: "sale" as const, area_sqm: 50, rooms: 2, price_cents: 15000000, currency: "EUR" as const, contact_email: "owner@example.com", is_published: true };
const inquiry: SaleInquiry = { id: 1, property_id: 7, title: property.title, asking_price_cents: property.price_cents, currency: "EUR", message: "Zanima me razgledanje stana.", owner_reply: "Vidimo se ispred ulaza.", viewing_at: "2030-09-25T12:00:00Z", status: "viewing_proposed", version: 2, created_at: "2030-09-01T12:00:00Z" };
beforeEach(() => { vi.resetAllMocks(); vi.mocked(api.saleInquiries).mockResolvedValue({ items: [inquiry], total: 1, has_next: false }); vi.mocked(api.updateSaleInquiry).mockResolvedValue(inquiry); });

it("retries a purchase inquiry with the same ID and without rental terms", async () => {
  vi.mocked(api.createSaleInquiry).mockRejectedValueOnce(new Error("offline")).mockResolvedValue(inquiry);
  const user = userEvent.setup();
  render(<SaleInquiryForm property={property} />);
  expect(screen.queryByLabelText("Željeno useljenje")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Pošalji upit za kupovinu" })).toBeDisabled();
  await user.type(screen.getByLabelText("Poruka prodavcu"), inquiry.message);
  await user.click(screen.getByRole("button", { name: "Pošalji upit za kupovinu" }));
  await screen.findByRole("alert");
  await user.click(screen.getByRole("button", { name: "Pošalji upit za kupovinu" }));
  await screen.findByText("Upit za kupovinu je poslat");
  const calls = vi.mocked(api.createSaleInquiry).mock.calls;
  expect(calls).toHaveLength(2);
  expect(calls[0]).toEqual(calls[1]);
  expect(calls[0]).toEqual([7, { message: inquiry.message, request_id: expect.any(String) }]);
  expect(screen.getByRole("link", { name: "Moji upiti za kupovinu" })).toHaveAttribute("href", "/sales");
});

it("shows total asking price and confirms the displayed sales viewing version", async () => {
  const user = userEvent.setup();
  render(<RentalInquiriesPage sale />);
  await screen.findByRole("heading", { name: property.title });
  expect(screen.queryByText(/mesec|Željeno useljenje/)).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Poruka kupca" })).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Prihvati termin" }));
  await waitFor(() => expect(api.updateSaleInquiry).toHaveBeenCalledWith(1, { action: "confirm", version: 2 }));
  expect(api.saleInquiries).toHaveBeenCalledWith(false, 0);
});

it("lets the seller propose a viewing through the sales API", async () => {
  const user = userEvent.setup();
  render(<RentalInquiriesPage owner sale />);
  expect(await screen.findByLabelText("Odgovor kupcu")).toBeVisible();
  fireEvent.change(screen.getByLabelText("Predloži termin razgledanja (opciono)"), { target: { value: "2030-09-26T14:00" } });
  await user.click(screen.getByRole("button", { name: "Pošalji predlog termina" }));
  await waitFor(() => expect(api.updateSaleInquiry).toHaveBeenCalledWith(1, { action: "propose", version: 2, owner_reply: inquiry.owner_reply, viewing_at: new Date("2030-09-26T14:00").toISOString() }));
  expect(api.saleInquiries).toHaveBeenCalledWith(true, 0);
});

it("exports a confirmed sales viewing with an identity separate from rentals", () => {
  expect(viewingCalendar(inquiry, "https://bookica.example")).toBeNull();
  const confirmed = { ...inquiry, status: "viewing_confirmed" as const };
  const file = viewingCalendar(confirmed, "https://bookica.example")!;
  expect(file.filename).toBe("bookica-prodaja-razgledanje-1.ics");
  expect(file.contents).toContain("UID:sale-viewing-1@bookica.example");
  expect(file.contents).toContain("URL:https://bookica.example/sales");
  expect(viewingCalendar(confirmed, "https://bookica.example", true)!.contents).toContain("URL:https://bookica.example/owner/sales");
});
