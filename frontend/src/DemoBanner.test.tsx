import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import DemoBanner from "./DemoBanner";

afterEach(() => vi.unstubAllGlobals());

it("shows the demo notice without exposing account credentials", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ demo: true }))));
  render(<DemoBanner />);
  expect(await screen.findByRole("note")).toHaveTextContent("DEMO");
  expect(screen.getByRole("note")).toHaveTextContent("ne unosite lične podatke");
});

it("does not label the ordinary app as a demo", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ demo: false }))));
  await act(async () => { render(<DemoBanner />); });
  expect(screen.queryByRole("note")).not.toBeInTheDocument();
});
