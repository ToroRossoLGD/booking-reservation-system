import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import OwnerPropertyAnalytics from "./OwnerPropertyAnalytics";
import PropertyViewTracker from "./PropertyViewTracker";
import { api } from "./api";
import type { AnalyticsMonth, PropertyAnalytics } from "./property-analytics-types";

vi.mock("./api", () => ({ api: { propertyAnalytics: vi.fn(), recordPropertyView: vi.fn() }, ApiError: class extends Error { constructor(message: string, public status: number) { super(message); } } }));
const data: PropertyAnalytics = { year: 2026, properties: [{ id: 7, title: "Stan na reci", offer_type: "short_stay" }], months: Array.from({ length: 12 }, (_, index): AnalyticsMonth => ({ month: index + 1, views: index === 0 ? 3 : 0, reservations: index === 0 ? 1 : 0, cancelled: 0, nights: index === 0 ? 2 : 0, booked_value_cents: index === 0 ? { EUR: 2000, USD: 1000 } : {} })) };
beforeEach(() => { vi.resetAllMocks(); sessionStorage.clear(); vi.mocked(api.propertyAnalytics).mockResolvedValue(data); vi.mocked(api.recordPropertyView).mockResolvedValue(undefined); });

it("shows monthly data and separate currencies and filters on the server", async () => {
  const user = userEvent.setup(); render(<OwnerPropertyAnalytics />);
  await screen.findByRole("heading", { name: "Pregled za 2026." });
  expect(screen.getByText(/Vrednost potvrđenih rezervacija:/)).toHaveTextContent(/€/);
  expect(screen.getByText(/Vrednost potvrđenih rezervacija:/)).toHaveTextContent(/\$/);
  const table = screen.getByRole("table");
  expect(within(table).getAllByRole("row")).toHaveLength(13);
  expect(within(table).getByRole("row", { name: /Januar/ })).toHaveTextContent(/Januar.*3.*1.*0.*2/);
  await user.selectOptions(screen.getByLabelText("Prikaži grafikon"), "views");
  expect(screen.getByText("Pregledi detalja po mesecima")).toBeVisible();
  await user.selectOptions(screen.getByLabelText("Oglas"), "7");
  await waitFor(() => expect(api.propertyAnalytics).toHaveBeenLastCalledWith(new Date().getFullYear(), 7, expect.any(AbortSignal)));
  await user.clear(screen.getByLabelText("Godina"));
  await user.type(screen.getByLabelText("Godina"), "2025");
  await user.click(screen.getByRole("button", { name: "Prikaži / osveži" }));
  await waitFor(() => expect(api.propertyAnalytics).toHaveBeenLastCalledWith(2025, 7, expect.any(AbortSignal)));
});

it("retries analytics failures and aborts requests when leaving", async () => {
  vi.mocked(api.propertyAnalytics).mockRejectedValueOnce(new Error("offline")).mockResolvedValue(data);
  const user = userEvent.setup(); const view = render(<OwnerPropertyAnalytics />);
  await user.click(await screen.findByRole("button", { name: "Pokušaj ponovo" }));
  await screen.findByRole("table");
  const signal = vi.mocked(api.propertyAnalytics).mock.calls.at(-1)![2]!;
  view.unmount();
  expect(signal.aborted).toBe(true);
});

it("reuses a daily session identifier across detail openings and swallows tracking failures", async () => {
  const first = render(<PropertyViewTracker propertyId={7} />);
  await waitFor(() => expect(api.recordPropertyView).toHaveBeenCalledTimes(1));
  const id = vi.mocked(api.recordPropertyView).mock.calls[0][1];
  expect(id).toMatch(/^[0-9a-f-]{36}$/);
  first.unmount();
  vi.mocked(api.recordPropertyView).mockRejectedValue(new Error("offline"));
  render(<PropertyViewTracker propertyId={7} />);
  await waitFor(() => expect(api.recordPropertyView).toHaveBeenLastCalledWith(7, id));
});

it("rotates the anonymous session identifier after a UTC day change", async () => {
  sessionStorage.setItem("bookica_view_session", "2000-01-01|00000000-0000-0000-0000-000000000000");
  render(<PropertyViewTracker propertyId={7} />);
  await waitFor(() => expect(api.recordPropertyView).toHaveBeenCalled());
  expect(vi.mocked(api.recordPropertyView).mock.calls[0][1]).not.toBe("00000000-0000-0000-0000-000000000000");
});
