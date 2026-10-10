import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import RentalInquiryForm from "./RentalInquiryForm";
import SaleInquiryForm from "./SaleInquiryForm";
import PropertyReportForm from "./PropertyReportForm";
import PropertyPhotoManager from "./PropertyPhotoManager";

vi.mock("./api", async importOriginal => ({ ...await importOriginal<typeof import("./api")>(), api: {
  createRentalInquiry: vi.fn(), createSaleInquiry: vi.fn(), reportProperty: vi.fn(), ownerPhotos: vi.fn(), uploadPropertyPhoto: vi.fn(),
} }));
const property = { id: 1, venue_id: 1, title: "Stan", description: "Stan u centru", city: "Beograd", offer_type: "long_term" as const, area_sqm: 50, rooms: 2, price_cents: 60000, currency: "EUR" as const, contact_email: "owner@example.com", is_published: true };
beforeEach(() => vi.resetAllMocks());

it.each([false, true])("keeps inquiry input and request IDs after a rate limit (sale=%s)", async sale => {
  const send = sale ? api.createSaleInquiry : api.createRentalInquiry;
  vi.mocked(send).mockRejectedValue(new ApiError("limited", 429, 60));
  render(sale ? <SaleInquiryForm property={{ ...property, offer_type: "sale" }} /> : <RentalInquiryForm property={property} />);
  if (!sale) fireEvent.change(screen.getByLabelText("Željeno useljenje"), { target: { value: "2035-10-01" } });
  const input = screen.getByLabelText(sale ? "Poruka prodavcu" : "Poruka vlasniku");
  await userEvent.type(input, "Zelim da pogledam stan u subotu.");
  const button = screen.getByRole("button", { name: sale ? "Pošalji upit za kupovinu" : "Pošalji upit za najam" });
  await userEvent.click(button);
  expect(await screen.findByRole("alert")).toHaveTextContent("Sačekajte 60 sekundi");
  expect(input).toHaveValue("Zelim da pogledam stan u subotu.");
  expect(send).toHaveBeenCalledTimes(1);
  await userEvent.click(button);
  expect(vi.mocked(send).mock.calls[0]).toEqual(vi.mocked(send).mock.calls[1]);
});

it.each([true, false])("distinguishes temporary report throttle from open-report quota (temporary=%s)", async temporary => {
  vi.mocked(api.reportProperty).mockRejectedValue(new ApiError("limited", 429, temporary ? 90 : undefined));
  render(<PropertyReportForm propertyId={1} />);
  await userEvent.click(screen.getByRole("button", { name: "Prijavi oglas" }));
  await userEvent.type(screen.getByLabelText("Opis problema"), "Informacije o ceni nisu tacne.");
  await userEvent.click(screen.getByRole("button", { name: "Pošalji prijavu" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(temporary ? "Sačekajte 90 sekundi" : "20 otvorenih prijava");
  expect(screen.getByLabelText("Opis problema")).toHaveValue("Informacije o ceni nisu tacne.");
});

it("keeps queued photos and the upload request ID after a rate limit", async () => {
  vi.mocked(api.ownerPhotos).mockResolvedValue([]);
  vi.mocked(api.uploadPropertyPhoto).mockRejectedValue(new ApiError("limited", 429, 120));
  render(<PropertyPhotoManager propertyId={1} title="Stan" />);
  await userEvent.upload(await screen.findByLabelText("Dodaj fotografije"), new File(["photo"], "stan.png", { type: "image/png" }));
  const button = screen.getByRole("button", { name: "Otpremi fotografije (1)" });
  await userEvent.click(button);
  expect(await screen.findByRole("alert")).toHaveTextContent("Sačekajte 120 sekundi");
  expect(screen.getByRole("button", { name: "Ukloni iz reda: stan.png" })).toBeVisible();
  expect(api.uploadPropertyPhoto).toHaveBeenCalledTimes(1);
  await userEvent.click(button);
  expect(vi.mocked(api.uploadPropertyPhoto).mock.calls[0]).toEqual(vi.mocked(api.uploadPropertyPhoto).mock.calls[1]);
});
