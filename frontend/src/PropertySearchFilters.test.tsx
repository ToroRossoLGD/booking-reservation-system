import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import PropertyHome from "./PropertyHome";
import { api } from "./api";

vi.mock("./api", () => ({ api: { properties: vi.fn() } }));
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear();
  vi.mocked(api.properties).mockResolvedValue({ items: [], total: 0, limit: 12, offset: 0, has_next: false });
});

it("applies price in cents and studio zero, then resets price on offer changes", async () => {
  const user = userEvent.setup(); render(<PropertyHome />);
  await user.click(screen.getByText("Napredni filteri i sortiranje"));
  expect(screen.getByLabelText("Cena od")).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Dugoročni najam" }));
  await user.click(screen.getByText("Napredni filteri i sortiranje"));
  await user.type(screen.getByLabelText("Cena od"), "500.25");
  await user.type(screen.getByLabelText("Cena do"), "700");
  await user.type(screen.getByLabelText(/Broj soba/), "0");
  await user.type(screen.getByLabelText("Kvadratura od (m²)"), "30");
  await user.selectOptions(screen.getByLabelText("Sortiranje"), "price_asc");
  await user.click(screen.getByRole("button", { name: "Primeni filtere" }));
  await waitFor(() => expect(api.properties).toHaveBeenLastCalledWith("", "long_term", 0, expect.anything(), { min_price_cents: 50025, max_price_cents: 70000, currency: "EUR", rooms: 0, min_area_sqm: 30, sort: "price_asc" }));
  await user.click(screen.getByRole("button", { name: "Prodaja" }));
  await waitFor(() => expect(api.properties).toHaveBeenLastCalledWith("", "sale", 0, expect.anything(), expect.objectContaining({ rooms: 0, min_area_sqm: 30, sort: "newest" })));
  expect(vi.mocked(api.properties).mock.lastCall?.[4]?.min_price_cents).toBeUndefined();
  await user.click(screen.getByRole("button", { name: "Obriši filtere" }));
  await waitFor(() => expect(api.properties).toHaveBeenLastCalledWith("", "", 0, expect.anything(), {}));
});

it("rejects reversed ranges before sending a request", async () => {
  const user = userEvent.setup(); render(<PropertyHome />);
  await user.click(screen.getByText("Napredni filteri i sortiranje"));
  await user.type(screen.getByLabelText("Kvadratura od (m²)"), "60");
  await user.type(screen.getByLabelText("Kvadratura do (m²)"), "40");
  const count = vi.mocked(api.properties).mock.calls.length;
  await user.click(screen.getByRole("button", { name: "Primeni filtere" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Minimalna vrednost ne može biti veća");
  expect(api.properties).toHaveBeenCalledTimes(count);
});
