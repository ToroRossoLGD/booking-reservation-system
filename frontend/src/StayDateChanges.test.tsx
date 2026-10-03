import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api } from "./api";
import StayDateChanges from "./StayDateChanges";
import type { Stay, StayChange, StayQuote } from "./stay-types";
import { propertyToday, shiftDate } from "./stay-types";

vi.mock("./api", () => ({ api: { stayChanges: vi.fn(), stayChangeQuote: vi.fn(), requestStayChange: vi.fn(), decideStayChange: vi.fn() }, ApiError: class extends Error {} }));
const today = propertyToday();
const stay: Stay = { id: 1, property_id: 7, check_in: shiftDate(today, 5), check_out: shiftDate(today, 8), guests: 2, status: "confirmed", title: "Stan", city: "Beograd", timezone: "Europe/Belgrade", contact_email: "host@example.com", nightly_rate_cents: 6500, total_cents: 19500, currency: "EUR", created_at: "2026-10-01T10:00:00Z", payment_method: "pay_on_arrival" };
const quote: StayQuote = { nights: 3, nightly_rate_cents: 7000, total_cents: 21000, currency: "EUR", timezone: stay.timezone, payment_method: "pay_on_arrival", check_in_time: "15:00", check_out_time: "10:00" };
const change: StayChange = { id: 8, stay_id: 1, check_in: shiftDate(today, 6), check_out: shiftDate(today, 9), original: stay, quote, status: "pending", created_at: stay.created_at, resolved_at: null };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.stayChanges).mockResolvedValue({ items: [], total: 0, has_next: false });
  vi.mocked(api.stayChangeQuote).mockResolvedValue(quote);
  vi.mocked(api.requestStayChange).mockResolvedValue(change);
});

it("loads history on demand, requires price consent and preserves request identity after failure", async () => {
  const user = userEvent.setup();
  render(<StayDateChanges stay={stay} owner={false} onChanged={vi.fn()} />);
  expect(api.stayChanges).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Promene termina" }));
  await screen.findByText("Nema zahteva za promenu termina.");
  fireEvent.change(screen.getByLabelText("Novi dolazak"), { target: { value: change.check_in } });
  fireEvent.change(screen.getByLabelText("Novi odlazak"), { target: { value: change.check_out } });
  await user.click(screen.getByRole("button", { name: "Proveri novi termin i cenu" }));
  const send = await screen.findByRole("button", { name: "Pošalji zahtev za promenu" });
  expect(send).toBeDisabled();
  await user.click(screen.getByRole("checkbox"));
  vi.mocked(api.requestStayChange).mockRejectedValueOnce(new Error("network"));
  await user.click(send);
  await screen.findByRole("alert");
  await user.click(send);
  await screen.findByText(/Zahtev je poslat/);
  expect(api.requestStayChange).toHaveBeenCalledTimes(2);
  const [first, second] = vi.mocked(api.requestStayChange).mock.calls;
  expect(first).toEqual(second);
  expect(first[1]).toMatchObject({ check_in: change.check_in, check_out: change.check_out, quote, guests: 2 });
});

it("invalidates quote and consent when dates change", async () => {
  const user = userEvent.setup(); render(<StayDateChanges stay={stay} owner={false} onChanged={vi.fn()} />);
  await user.click(screen.getByRole("button", { name: "Promene termina" }));
  await screen.findByText("Nema zahteva za promenu termina.");
  await user.click(screen.getByRole("button", { name: "Proveri novi termin i cenu" }));
  await user.click(await screen.findByRole("checkbox"));
  fireEvent.change(screen.getByLabelText("Novi dolazak"), { target: { value: change.check_in } });
  expect(screen.queryByRole("button", { name: "Pošalji zahtev za promenu" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Proveri novi termin i cenu" }));
  expect(await screen.findByRole("checkbox")).not.toBeChecked();
});

it("shows owner decisions, preserves the pending state on conflict and refreshes after success", async () => {
  vi.mocked(api.stayChanges).mockResolvedValue({ items: [change], total: 1, has_next: false });
  vi.mocked(api.decideStayChange).mockRejectedValueOnce(new Error("conflict")).mockResolvedValueOnce({ ...change, status: "accepted" });
  const onChanged = vi.fn(); const user = userEvent.setup();
  render(<StayDateChanges stay={stay} owner onChanged={onChanged} />);
  await user.click(screen.getByRole("button", { name: "Promene termina" }));
  const accept = await screen.findByRole("button", { name: "Odobri termin i cenu" });
  expect(screen.queryByRole("button", { name: "Povuci zahtev" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Novi dolazak")).not.toBeInTheDocument();
  await user.click(accept);
  await screen.findByRole("alert"); expect(onChanged).not.toHaveBeenCalled();
  await user.click(accept);
  await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  expect(api.decideStayChange).toHaveBeenLastCalledWith(1, 8, "accept");
});

it("offers guest withdrawal and aborts history when closed", async () => {
  vi.mocked(api.stayChanges).mockResolvedValue({ items: [change], total: 1, has_next: false });
  vi.mocked(api.decideStayChange).mockResolvedValue({ ...change, status: "withdrawn" });
  const user = userEvent.setup(); render(<StayDateChanges stay={stay} owner={false} onChanged={vi.fn()} />);
  await user.click(screen.getByRole("button", { name: "Promene termina" }));
  await user.click(await screen.findByRole("button", { name: "Povuci zahtev" }));
  expect(api.decideStayChange).toHaveBeenCalledWith(1, 8, "withdraw");
  const signal = vi.mocked(api.stayChanges).mock.calls.at(-1)![2]!;
  await user.click(screen.getByRole("button", { name: "Promene termina" }));
  expect(signal.aborted).toBe(true);
});

it("refreshes the booking when a retried submission has already been approved", async () => {
  vi.mocked(api.requestStayChange).mockResolvedValue({ ...change, status: "accepted" });
  const onChanged = vi.fn(); const user = userEvent.setup();
  render(<StayDateChanges stay={stay} owner={false} onChanged={onChanged} />);
  await user.click(screen.getByRole("button", { name: "Promene termina" }));
  await screen.findByText("Nema zahteva za promenu termina.");
  await user.click(screen.getByRole("button", { name: "Proveri novi termin i cenu" }));
  await user.click(await screen.findByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Pošalji zahtev za promenu" }));
  await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  expect(screen.queryByText(/Dosadašnji termin ostaje potvrđen/)).not.toBeInTheDocument();
});
