import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import RentalTermsDisplay from "./RentalTermsDisplay";
import RentalTermsFields from "./RentalTermsFields";
import RentalInquiryForm from "./RentalInquiryForm";
import { readRentalTerms } from "./rental-terms";

vi.mock("./api", () => ({ api: { createRentalInquiry: vi.fn() }, ApiError: class extends Error {} }));

it("distinguishes missing terms from explicitly free deposit and bills", () => {
  const { rerender } = render(<RentalTermsDisplay terms={{}} currency="EUR" />);
  expect(screen.queryByRole("region")).not.toBeInTheDocument();
  rerender(<RentalTermsDisplay terms={{ deposit_cents: 0, monthly_bills_cents: 0, pets_policy: "by_agreement" }} currency="EUR" snapshot />);
  expect(screen.getByRole("region", { name: "Uslovi pri slanju upita" })).toHaveTextContent("Bez depozita");
  expect(screen.getByText(/Okvirni mesečni troškovi/)).toHaveTextContent("0");
  expect(screen.getByText("Ljubimci: Po dogovoru")).toBeVisible();
});

it("reads amounts in cents and clears all terms for other offer types", () => {
  const { container } = render(<form><RentalTermsFields value={{ deposit_cents: 0, monthly_bills_cents: 12345, minimum_rental_months: 6, pets_policy: "allowed", available_from: "2030-10-01" }} /></form>);
  const fields = new FormData(container.querySelector("form")!);
  expect(readRentalTerms(fields, true)).toEqual({ deposit_cents: 0, monthly_bills_cents: 12345, minimum_rental_months: 6, pets_policy: "allowed", available_from: "2030-10-01" });
  expect(Object.values(readRentalTerms(fields, false))).toEqual([null, null, null, null, null]);
  fireEvent.change(screen.getByLabelText("Depozit"), { target: { value: "" } });
  expect(readRentalTerms(new FormData(container.querySelector("form")!), true).deposit_cents).toBeNull();
});

it("applies the advertised availability and minimum duration to an inquiry", () => {
  const property = { id: 1, venue_id: 1, title: "Stan", description: "Stan za dugorocni najam", city: "Beograd", offer_type: "long_term" as const, area_sqm: 50, rooms: 2, price_cents: 60000, currency: "EUR" as const, contact_email: "owner@example.com", is_published: true, available_from: "2099-10-01", minimum_rental_months: 24 };
  render(<RentalInquiryForm property={property} />);
  const date = screen.getByLabelText("Željeno useljenje");
  const months = screen.getByLabelText("Trajanje najma (meseci)");
  expect(date).toHaveAttribute("min", "2099-10-01");
  expect(months).toHaveAttribute("min", "24");
  expect(months).toHaveValue(24);
  fireEvent.change(date, { target: { value: "2099-09-30" } });
  fireEvent.change(months, { target: { value: "23" } });
  expect(date).toBeInvalid();
  expect(months).toBeInvalid();
});
