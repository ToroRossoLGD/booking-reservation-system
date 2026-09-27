import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api } from "./api";
import PropertyReviews from "./PropertyReviews";
import StayReview from "./StayReview";

vi.mock("./api", () => ({ api: { propertyReviews: vi.fn(), stayReview: vi.fn(), createPropertyReview: vi.fn() }, ApiError: class extends Error {} }));
const review = { id: 1, rating: 4, comment: "Uredan stan, odlicna lokacija.", created_at: "2030-01-02T12:00:00Z" };
beforeEach(() => vi.resetAllMocks());

it("loads public reviews on demand and paginates with the server aggregate", async () => {
  vi.mocked(api.propertyReviews).mockResolvedValue({ items: [review], total: 11, average_rating: 4.5, has_next: true });
  const user = userEvent.setup(); render(<PropertyReviews propertyId={7} />);
  expect(api.propertyReviews).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Prikaži recenzije gostiju" }));
  expect(await screen.findByText(/Prosečna ocena: 4,5/)).toBeVisible();
  expect(screen.getByText(review.comment)).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Sledeće recenzije" }));
  await waitFor(() => expect(api.propertyReviews).toHaveBeenLastCalledWith(7, 10, expect.any(AbortSignal)));
});

it("retries a failed review listing and renders comments as plain text", async () => {
  vi.mocked(api.propertyReviews).mockRejectedValueOnce(new Error("network")).mockResolvedValue({ items: [{ ...review, comment: "<script>alert('x')</script>" }], total: 1, average_rating: 4, has_next: false });
  const user = userEvent.setup(); const { container } = render(<PropertyReviews propertyId={7} />);
  await user.click(screen.getByRole("button", { name: "Prikaži recenzije gostiju" }));
  await user.click(await screen.findByRole("button", { name: "Pokušaj ponovo" }));
  expect(await screen.findByText("<script>alert('x')</script>")).toBeVisible();
  expect(container.querySelector("script")).toBeNull();
});

it("preserves review text for a safe retry and displays the saved review", async () => {
  vi.mocked(api.stayReview).mockResolvedValue(null);
  vi.mocked(api.createPropertyReview).mockRejectedValueOnce(new Error("network")).mockResolvedValue(review);
  const user = userEvent.setup(); render(<StayReview stayId={9} />);
  await user.click(screen.getByRole("button", { name: "Oceni boravak / moja recenzija" }));
  await user.selectOptions(await screen.findByLabelText("Ocena"), "4");
  await user.type(screen.getByLabelText("Komentar"), review.comment);
  await user.click(screen.getByRole("button", { name: "Objavi recenziju" }));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Komentar")).toHaveValue(review.comment);
  await user.click(screen.getByRole("button", { name: "Objavi recenziju" }));
  expect(await screen.findByText("Tvoja ocena: 4 / 5")).toBeVisible();
  expect(api.createPropertyReview).toHaveBeenNthCalledWith(1, 9, { rating: 4, comment: review.comment });
  expect(api.createPropertyReview).toHaveBeenNthCalledWith(2, 9, { rating: 4, comment: review.comment });
  expect(screen.queryByRole("button", { name: "Objavi recenziju" })).not.toBeInTheDocument();
});

it("opens an existing review without offering another submission", async () => {
  vi.mocked(api.stayReview).mockResolvedValue(review);
  const user = userEvent.setup(); render(<StayReview stayId={9} />);
  await user.click(screen.getByRole("button", { name: "Oceni boravak / moja recenzija" }));
  expect(await screen.findByText(review.comment)).toBeVisible();
  expect(screen.queryByLabelText("Ocena")).not.toBeInTheDocument();
});
