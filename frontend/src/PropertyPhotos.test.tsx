import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import PropertyGallery from "./PropertyGallery";
import PropertyPhotoManager from "./PropertyPhotoManager";

vi.mock("./api", () => ({ api: { ownerPhotos: vi.fn(), uploadPropertyPhoto: vi.fn(), reorderPropertyPhotos: vi.fn(), deletePropertyPhoto: vi.fn(), ownerPhotoBlob: vi.fn(), propertyPhotoUrl: (id: number, photoId: number, thumb = false) => `/api/properties/${id}/photos/${photoId}/image?thumbnail=${thumb}` }, ApiError: class extends Error { status: number; constructor(message: string, status: number) { super(message); this.status = status; } } }));
const photos = [{ id: 1, property_id: 7, position: 0, width: 40, height: 30 }, { id: 2, property_id: 7, position: 1, width: 40, height: 30 }];
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.ownerPhotos).mockResolvedValue(photos);
  vi.mocked(api.ownerPhotoBlob).mockResolvedValue(new Blob(["image"], { type: "image/jpeg" }));
  vi.mocked(api.reorderPropertyPhotos).mockResolvedValue([photos[1], photos[0]]);
  vi.mocked(api.deletePropertyPhoto).mockResolvedValue(undefined);
  URL.createObjectURL = vi.fn(() => "blob:preview");
  URL.revokeObjectURL = vi.fn();
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
});

it("opens the gallery, navigates images and closes it", async () => {
  const user = userEvent.setup();
  render(<PropertyGallery photos={photos} title="Stan sa terasom" />);
  await user.click(screen.getByRole("button", { name: "Otvori galeriju: Stan sa terasom" }));
  expect(screen.getByRole("dialog")).toBeVisible();
  expect(screen.getByRole("img", { name: "Stan sa terasom — fotografija 1" })).toHaveAttribute("src", expect.stringContaining("/photos/1/"));
  await user.click(screen.getByRole("button", { name: "Sledeća fotografija" }));
  expect(screen.getByRole("img", { name: "Stan sa terasom — fotografija 2" })).toHaveAttribute("src", expect.stringContaining("/photos/2/"));
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "ArrowLeft" });
  expect(screen.getByRole("status")).toHaveTextContent("1 / 2");
  await user.click(screen.getByRole("button", { name: "Zatvori galeriju" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("shows a retry control for unavailable gallery images", async () => {
  const user = userEvent.setup();
  render(<PropertyGallery photos={photos} title="Stan" />);
  await user.click(screen.getByRole("button", { name: "Otvori galeriju: Stan" }));
  fireEvent.error(screen.getByRole("img", { name: "Stan — fotografija 1" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Fotografija nije dostupna");
  await user.click(screen.getByRole("button", { name: "Pokušaj ponovo" }));
  expect(screen.getByRole("img", { name: "Stan — fotografija 1" })).toBeInTheDocument();
});

it("selects a cover and requires confirmation to delete", async () => {
  const user = userEvent.setup();
  render(<PropertyPhotoManager propertyId={7} title="Stan" />);
  await user.click(await screen.findByRole("button", { name: "Postavi fotografiju 2 kao naslovnu" }));
  await waitFor(() => expect(api.reorderPropertyPhotos).toHaveBeenCalledWith(7, [2, 1]));
  await user.click(screen.getByRole("button", { name: "Obriši fotografiju 1" }));
  expect(api.deletePropertyPhoto).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Potvrdi brisanje" }));
  await waitFor(() => expect(api.deletePropertyPhoto).toHaveBeenCalledWith(7, 2));
});

it("retains only failed uploads with the same request identifier for retry", async () => {
  vi.mocked(api.ownerPhotos).mockResolvedValue([]);
  vi.mocked(api.uploadPropertyPhoto).mockResolvedValueOnce(photos[0]).mockRejectedValueOnce(new Error("offline")).mockResolvedValue(photos[1]);
  const user = userEvent.setup();
  render(<PropertyPhotoManager propertyId={7} title="Stan" />);
  await user.upload(await screen.findByLabelText("Dodaj fotografije"), [new File(["one"], "one.png", { type: "image/png" }), new File(["two"], "two.png", { type: "image/png" })]);
  await user.click(screen.getByRole("button", { name: "Otpremi fotografije (2)" }));
  await screen.findByRole("alert");
  expect(screen.queryByRole("button", { name: "Ukloni iz reda: one.png" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Otpremi fotografije (1)" }));
  await waitFor(() => expect(api.uploadPropertyPhoto).toHaveBeenCalledTimes(3));
  expect(vi.mocked(api.uploadPropertyPhoto).mock.calls[1]).toEqual(vi.mocked(api.uploadPropertyPhoto).mock.calls[2]);
});

it("rejects oversized batches and explains unavailable storage", async () => {
  vi.mocked(api.ownerPhotos).mockResolvedValue([]);
  vi.mocked(api.uploadPropertyPhoto).mockRejectedValue(new ApiError("Not configured", 503));
  const user = userEvent.setup();
  render(<PropertyPhotoManager propertyId={7} title="Stan" />);
  const input = await screen.findByLabelText("Dodaj fotografije");
  await user.upload(input, Array.from({ length: 13 }, (_, i) => new File(["photo"], `${i}.png`, { type: "image/png" })));
  expect(screen.getByRole("alert")).toHaveTextContent("najviše 12");
  expect(api.uploadPropertyPhoto).not.toHaveBeenCalled();
  await user.upload(input, new File(["photo"], "one.png", { type: "image/png" }));
  await user.click(screen.getByRole("button", { name: "Otpremi fotografije (1)" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("još nije podešeno");
});
