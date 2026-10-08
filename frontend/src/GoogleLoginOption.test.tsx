import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { GoogleLoginOption } from "./GoogleLoginOption";

afterEach(() => vi.unstubAllGlobals());

it("shows Google only after the API confirms it is configured", async () => {
  let resolve!: (value: Response) => void;
  const fetchMock = vi.fn(() => new Promise<Response>((done) => { resolve = done; }));
  vi.stubGlobal("fetch", fetchMock);
  render(<GoogleLoginOption />);
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  await act(async () => resolve(new Response(JSON.stringify({ google: true }))));
  expect(await screen.findByRole("button", { name: "Log in with Google" })).toBeVisible();
  expect(screen.getByText("or log in with email")).toBeVisible();
  expect(fetchMock).toHaveBeenCalledWith("/api/auth/providers", expect.objectContaining({ cache: "no-store" }));
});

it.each([false, "true", null])("hides disabled or invalid provider flags: %s", async (google) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ google }))));
  await act(async () => { render(<GoogleLoginOption />); });
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  expect(screen.queryByText("or log in with email")).not.toBeInTheDocument();
});

it.each(["network", "server", "json"])("hides unavailable providers on %s failure", async (failure) => {
  vi.stubGlobal("fetch", failure === "network"
    ? vi.fn().mockRejectedValue(new Error("offline"))
    : vi.fn().mockResolvedValue(new Response(failure === "json" ? "invalid" : "{}", { status: failure === "server" ? 503 : 200 })));
  await act(async () => { render(<GoogleLoginOption />); });
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it("aborts discovery when the modal is closed", () => {
  const fetchMock = vi.fn(() => new Promise<Response>(() => {}));
  vi.stubGlobal("fetch", fetchMock);
  const { unmount } = render(<GoogleLoginOption />);
  const options = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
  unmount();
  expect(options[1].signal?.aborted).toBe(true);
});
