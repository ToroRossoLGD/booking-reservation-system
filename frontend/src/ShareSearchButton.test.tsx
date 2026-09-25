import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import ShareSearchButton from "./ShareSearchButton";

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
});
