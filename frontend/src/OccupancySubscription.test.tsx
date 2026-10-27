import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import OccupancySubscription from "./OccupancySubscription";

vi.mock("./api", () => ({ api: { occupancyFeedStatus: vi.fn(), rotateOccupancyFeed: vi.fn(), revokeOccupancyFeed: vi.fn() }, occupancySubscriptionUrl: (path: string) => `https://example.test/api${path}` }));
afterEach(() => { vi.resetAllMocks(); localStorage.clear(); });

it("loads on demand, requires confirmation and removes the secret after revocation", async () => {
  vi.mocked(api.occupancyFeedStatus).mockResolvedValue({ active: false });
  vi.mocked(api.rotateOccupancyFeed).mockResolvedValue({ active: true, path: "/occupancy-feeds/secret.ics" });
  vi.mocked(api.revokeOccupancyFeed).mockResolvedValue({ active: false });
  render(<OccupancySubscription propertyId={7} />);
  expect(api.occupancyFeedStatus).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Podesi iCal pretplatu"));
  fireEvent.click(await screen.findByText("Kreiraj pretplatni link"));
  expect(screen.getByText("Odustani")).toHaveFocus();
  expect(api.rotateOccupancyFeed).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Odustani"));
  fireEvent.click(screen.getByText("Kreiraj pretplatni link"));
  fireEvent.click(screen.getByText("Potvrdi promenu"));
  expect(await screen.findByLabelText("Tajni pretplatni link")).toHaveValue("https://example.test/api/occupancy-feeds/secret.ics");
  expect(screen.getByLabelText("Tajni pretplatni link")).toHaveFocus();
  fireEvent.click(screen.getByText("Opozovi pretplatu"));
  expect(api.revokeOccupancyFeed).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Potvrdi promenu"));
  expect(await screen.findByText("Pretplata nije aktivna.")).toBeVisible();
  expect(screen.queryByLabelText("Tajni pretplatni link")).toBeNull();
  expect(api.revokeOccupancyFeed).toHaveBeenCalledWith(7);
});

it("allows retry after a status failure and discards a secret after a session change", async () => {
  localStorage.setItem("bookica_token", "first");
  vi.mocked(api.occupancyFeedStatus).mockRejectedValueOnce(new Error("offline")).mockResolvedValue({ active: true });
  let resolve!: (value: { active: boolean; path: string }) => void;
  vi.mocked(api.rotateOccupancyFeed).mockImplementation(() => new Promise(done => { resolve = done; }));
  render(<OccupancySubscription propertyId={7} />);
  fireEvent.click(screen.getByText("Podesi iCal pretplatu"));
  expect(await screen.findByRole("alert")).toBeVisible();
  fireEvent.click(screen.getByText("Proveri status pretplate"));
  fireEvent.click(await screen.findByText("Zameni pretplatni link"));
  fireEvent.click(screen.getByText("Potvrdi promenu"));
  expect(screen.getByText("Potvrdi promenu")).toBeDisabled();
  localStorage.setItem("bookica_token", "second");
  await act(async () => { resolve({ active: true, path: "/occupancy-feeds/old-account.ics" }); });
  expect(screen.queryByLabelText("Tajni pretplatni link")).toBeNull();
});
