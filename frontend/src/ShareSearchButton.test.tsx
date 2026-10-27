import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import ShareSearchButton from "./ShareSearchButton";

afterEach(() => vi.restoreAllMocks());

it("copies the supplied search URL and exposes a selectable fallback if clipboard access fails", async () => {
  const user = userEvent.setup();
  const path = "/?city=Novi+Sad&rooms=0&offset=12";
  render(<ShareSearchButton path={path} />);
  const copy = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
  await user.click(screen.getByRole("button", { name: "Kopiraj link pretrage" }));
  expect(copy).toHaveBeenCalledWith(`${window.location.origin}${path}`);
  expect(screen.getByRole("status")).toHaveTextContent("Link pretrage je kopiran.");
  copy.mockRejectedValue(new Error("denied"));
  await user.click(screen.getByRole("button", { name: "Kopiraj link pretrage" }));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Kopiraj link pretrage ručno")).toHaveValue(`${window.location.origin}${path}`);
  const input = screen.getByLabelText("Kopiraj link pretrage ručno") as HTMLInputElement;
  expect(input).toHaveFocus();
  expect(input).toHaveAccessibleDescription(/Link je označen za ručno kopiranje/);
  expect(input.selectionStart).toBe(0);
  expect(input.selectionEnd).toBe(input.value.length);
  await user.click(screen.getByRole("button", { name: "Kopiraj link pretrage" }));
  expect(screen.getByLabelText("Kopiraj link pretrage ručno")).toHaveFocus();
  copy.mockResolvedValue(undefined);
  await user.click(screen.getByRole("button", { name: "Kopiraj link pretrage" }));
  expect(screen.getByRole("status")).toHaveTextContent("Link pretrage je kopiran.");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Kopiraj link pretrage ručno")).not.toBeInTheDocument();
});

it("clears feedback when filters change and ignores an older pending copy", async () => {
  const user = userEvent.setup();
  const view = render(<ShareSearchButton path="/?city=Beograd" />);
  let resolve!: () => void;
  const pending = new Promise<void>(done => { resolve = done; });
  const copy = vi.spyOn(navigator.clipboard, "writeText").mockReturnValueOnce(pending).mockResolvedValue(undefined);
  await user.click(screen.getByRole("button"));
  expect(screen.getByRole("button", { name: "Kopiranje…" })).toBeDisabled();
  await user.click(screen.getByRole("button"));
  expect(copy).toHaveBeenCalledTimes(1);
  view.rerender(<ShareSearchButton path="/?city=Nis" />);
  expect(screen.getByRole("button", { name: "Kopiraj link pretrage" })).toBeEnabled();
  await act(async () => { resolve(); await pending; });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button"));
  expect(copy).toHaveBeenLastCalledWith(`${window.location.origin}/?city=Nis`);
  expect(screen.getByRole("status")).toBeVisible();
  view.rerender(<ShareSearchButton path="/?city=Nis&rooms=2" />);
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("discards the previous manual fallback when the search changes", async () => {
  const user = userEvent.setup();
  const view = render(<ShareSearchButton path="/?city=Beograd" />);
  vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("denied"));
  await user.click(screen.getByRole("button"));
  expect(screen.getByRole("alert")).toBeVisible();
  view.rerender(<ShareSearchButton path="/?city=Nis" />);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button"));
  expect(screen.getByRole("textbox")).toHaveValue(`${window.location.origin}/?city=Nis`);
});
