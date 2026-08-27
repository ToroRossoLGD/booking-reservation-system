import { describe, expect, it } from "vitest";
import { parseApplicationRoute } from "./routing";

describe("parseApplicationRoute", () => {
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
