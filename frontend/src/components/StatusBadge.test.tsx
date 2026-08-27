import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders readable text and a status styling hook", () => {
    render(<StatusBadge value="checked_in" />);

    const badge = screen.getByText("checked in");
    expect(badge).toHaveClass("status-checked_in");
    expect(badge).toHaveAttribute("data-status", "checked_in");
  });
});
