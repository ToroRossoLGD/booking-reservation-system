import { afterEach, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("uses Retry-After on 429 without retrying automatically", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Too many" }), { status: 429, headers: { "Retry-After": "45" } }));
  vi.stubGlobal("fetch", fetch);
  await expect(api.requestPasswordReset("guest@example.com")).rejects.toMatchObject({ status: 429, retryAfter: 45, message: "Previše pokušaja. Sačekajte 45 sekundi pa pokušajte ponovo." });
  expect(fetch).toHaveBeenCalledTimes(1);
});

it.each(["", "invalid", "-2", "9999999999"])("does not display an invalid wait value %s", async retry => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 429, headers: { "Retry-After": retry } })));
  await expect(api.requestEmailVerification()).rejects.toMatchObject({ retryAfter: undefined, message: "Previše pokušaja. Sačekajte pre novog zahteva." });
});

it("keeps other API errors intact", () => {
  expect(new ApiError("Invalid link", 410).message).toBe("Invalid link");
});
