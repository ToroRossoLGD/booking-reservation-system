import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api } from "./api";
import RentalConversation from "./RentalConversation";
import type { RentalMessage, RentalMessagePage } from "./rental-types";

vi.mock("./api", () => ({ api: { rentalMessages: vi.fn(), sendRentalMessage: vi.fn(), readRentalMessages: vi.fn() }, ApiError: class extends Error {} }));
const message: RentalMessage = { id: 2, sender: "owner", kind: "message", body: "Slobodan je termin u subotu.", viewing_at: null, created_at: "2030-01-01T12:00:00Z", read_at: null };
const page: RentalMessagePage = { items: [message], has_more: false, next_before_id: null, unread_count: 1 };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.rentalMessages).mockResolvedValue(page);
  vi.mocked(api.sendRentalMessage).mockResolvedValue({ ...message, id: 3, sender: "tenant" });
  vi.mocked(api.readRentalMessages).mockResolvedValue({ unread_count: 0 });
});

it("loads history only when opened and marks only displayed incoming messages read", async () => {
  const user = userEvent.setup();
  vi.mocked(api.rentalMessages).mockResolvedValue({ ...page, items: [message, { ...message, id: 3, sender: "tenant" }] });
  render(<RentalConversation inquiryId={7} owner={false} active unreadCount={1} />);
  expect(api.rentalMessages).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: /Otvori razgovor/ }));
  await user.click(await screen.findByRole("button", { name: "Označi prikazane poruke kao pročitane" }));
  await waitFor(() => expect(api.readRentalMessages).toHaveBeenCalledWith(7, [2]));
  expect(screen.queryByText("1 nepročitanih")).not.toBeInTheDocument();
});

it("retains draft and request ID when retrying after a network error", async () => {
  vi.mocked(api.sendRentalMessage).mockRejectedValueOnce(new Error("offline")).mockResolvedValue({ ...message, id: 3 });
  const user = userEvent.setup();
  render(<RentalConversation inquiryId={7} owner={false} active />);
  await user.click(screen.getByRole("button", { name: /Otvori razgovor/ }));
  await screen.findByText(message.body);
  await user.type(screen.getByLabelText("Nova poruka"), "Može li u 14h?");
  await user.click(screen.getByRole("button", { name: "Pošalji poruku" }));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Nova poruka")).toHaveValue("Može li u 14h?");
  await user.click(screen.getByRole("button", { name: "Pošalji poruku" }));
  await screen.findByText("Poruka je poslata.");
  expect(vi.mocked(api.sendRentalMessage).mock.calls[0]).toEqual(vi.mocked(api.sendRentalMessage).mock.calls[1]);
  expect(screen.getByLabelText("Nova poruka")).toHaveValue("");
});

it("loads older history using the cursor and retains new-message unread count", async () => {
  vi.mocked(api.rentalMessages).mockResolvedValueOnce({ ...page, has_more: true, next_before_id: 2 }).mockResolvedValue({ ...page, items: [{ ...message, id: 1, kind: "legacy_reply", created_at: null }], unread_count: 3 });
  const user = userEvent.setup();
  render(<RentalConversation inquiryId={7} owner={false} active />);
  await user.click(screen.getByRole("button", { name: /Otvori razgovor/ }));
  await user.click(await screen.findByRole("button", { name: "Starije poruke" }));
  await screen.findByText("Datum ranijeg odgovora nije zabeležen.");
  expect(api.rentalMessages).toHaveBeenLastCalledWith(7, 2);
  expect(screen.getByText("3 nepročitanih")).toBeInTheDocument();
});

it("keeps closed conversations readable without a composer", async () => {
  const user = userEvent.setup();
  render(<RentalConversation inquiryId={7} owner={false} active={false} />);
  await user.click(screen.getByRole("button", { name: /Otvori razgovor/ }));
  await screen.findByText(message.body);
  expect(screen.queryByLabelText("Nova poruka")).not.toBeInTheDocument();
  expect(screen.getByText(/Istorija razgovora ostaje dostupna/)).toBeInTheDocument();
});

it("does not interpret markup as HTML and keeps unread state on read failure", async () => {
  vi.mocked(api.rentalMessages).mockResolvedValue({ ...page, items: [{ ...message, body: '<img src=x onerror="alert(1)">' }] });
  vi.mocked(api.readRentalMessages).mockRejectedValue(new Error("offline"));
  const user = userEvent.setup();
  render(<RentalConversation inquiryId={7} owner={false} active unreadCount={1} />);
  await user.click(screen.getByRole("button", { name: /Otvori razgovor/ }));
  await screen.findByText('<img src=x onerror="alert(1)">');
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Označi prikazane poruke kao pročitane" }));
  await screen.findByRole("alert");
  expect(screen.getByText("1 nepročitanih")).toBeInTheDocument();
});
