import { describe, expect, it } from "vitest";
import { isKnownPage, normalizePagePath, parseApplicationRoute } from "./routing";

describe("parseApplicationRoute", () => {
  it("opens the notification inbox directly", () => {
    expect(parseApplicationRoute("/account/notifications")).toEqual({ page: "account", accountTab: "notifications" });
    expect(parseApplicationRoute("/account/notifications/")).toEqual({ page: "account", accountTab: "notifications" });
  });
  it("extracts a customer reservation route", () => {
    expect(parseApplicationRoute("/account/reservations/42")).toEqual({
      page: "account",
      reservationId: 42,
    });
  });

  it("extracts an owner venue route", () => {
    expect(parseApplicationRoute("/owner/venues/7/")).toEqual({
      page: "owner",
      ownerVenueId: 7,
    });
  });

  it("falls back safely for unknown paths", () => {
    expect(parseApplicationRoute("/not-a-page")).toEqual({ page: "home" });
  });
});

it.each(["/", "/booking", "/account", "/owner", "/saved", "/stays", "/rentals", "/sales", "/owner/stays", "/owner/rentals", "/owner/sales", "/account/security", "/account/notifications", "/owner/analytics", "/moderation", "/forgot-password", "/reset-password", "/verify-email", "/account/reservations/42", "/owner/venues/7", "/owner/properties/7/preview", "/properties/7", "/properties/invalid"])("recognizes supported route %s", path => {
  expect(isKnownPage(path)).toBe(true);
  if (path !== "/") expect(isKnownPage(`${path}/`)).toBe(true);
});

it.each(["/missing", "/account/unknown", "/owner/unknown", "/booking/unknown", "/owner/venues/nope", "/account/reservations/42/extra"])("does not send unknown route %s to the legacy app", path => {
  expect(isKnownPage(path)).toBe(false);
});

it("normalizes only one trailing slash without rewriting encoded path content", () => {
  expect(normalizePagePath("/saved/")).toBe("/saved");
  expect(normalizePagePath("/saved//")).toBe("/saved//");
  expect(isKnownPage("/saved//")).toBe(false);
  expect(normalizePagePath("/unknown%2Fpath/")).toBe("/unknown%2Fpath");
});
