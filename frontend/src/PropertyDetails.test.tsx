import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import PropertyFacts from "./PropertyFacts";
import PropertyDetailFields from "./PropertyDetailFields";
import PropertySearchFilters from "./PropertySearchFilters";
import { readDetails } from "./property-details";
import { propertySearchPath, readPropertySearch } from "./property-search-url";

it("distinguishes missing details from ground floor and explicit no", () => {
  const { rerender } = render(<PropertyFacts property={{ floor: 0, property_type: "house", has_elevator: false, has_parking: true }} />);
  expect(screen.getByText("Prizemlje")).toBeVisible();
  expect(screen.getByText("Kuća")).toBeVisible();
  expect(screen.getByText("Ne")).toBeVisible();
  expect(screen.queryByText("Terasa")).not.toBeInTheDocument();
  rerender(<PropertyFacts property={{}} />);
  expect(screen.queryByLabelText("Karakteristike nekretnine")).not.toBeInTheDocument();
});

it("keeps edited values and explicitly clears unspecified details", async () => {
  const save = vi.fn(); const user = userEvent.setup();
  render(<form onSubmit={event => { event.preventDefault(); save(readDetails(new FormData(event.currentTarget))); }}><PropertyDetailFields value={{ property_type: "apartment", floor: 0, has_parking: false, neighborhood: "Liman" }} /><button>Sačuvaj</button></form>);
  expect(screen.getByRole("spinbutton", { name: /Sprat/ })).toHaveValue(0);
  await user.selectOptions(screen.getByLabelText("Parking"), "");
  await user.selectOptions(screen.getByLabelText("Tip nekretnine"), "house");
  await user.click(screen.getByRole("button", { name: "Sačuvaj" }));
  expect(save).toHaveBeenCalledWith(expect.objectContaining({ property_type: "house", floor: 0, has_parking: null, neighborhood: "Liman", has_elevator: null }));
});

it("submits false and zero filters and round-trips them in shareable URLs", async () => {
  const onApply = vi.fn(); const user = userEvent.setup();
  render(<PropertySearchFilters offer="sale" value={{ floor: 0, has_elevator: false, property_type: "house" }} onApply={onApply} />);
  await user.click(screen.getByText("Napredni filteri i sortiranje"));
  await user.type(screen.getByLabelText("Naselje"), "Novi grad");
  await user.selectOptions(screen.getByLabelText("Parking"), "true");
  await user.click(screen.getByRole("button", { name: "Primeni filtere" }));
  const filters = onApply.mock.calls[0][0];
  expect(filters).toMatchObject({ floor: 0, has_elevator: false, has_parking: true, property_type: "house", neighborhood: "Novi grad" });
  const path = propertySearchPath({ city: "Beograd", offer: "sale", offset: 12, filters });
  expect(readPropertySearch(path.slice(1))).toMatchObject({ offset: 12, filters: { floor: 0, has_elevator: false, has_parking: true, property_type: "house", neighborhood: "Novi grad" } });
});

it("ignores malformed shared detail filters", () => {
  expect(readPropertySearch("?property_type=castle&floor=-3&has_parking=no&heating=invalid&furnishing=invalid").filters).toEqual({});
  expect(readPropertySearch("?floor=-1&has_parking=false").filters).toEqual({ floor: -1, has_parking: false });
});
