import { expect, it } from "vitest";
import { ApiError } from "./api";
import { accountAccessError } from "./account-access-error";

it.each([401, 403, 409, 422, 500, 503])("uses controlled Serbian copy for status %s", status => {
  const message = accountAccessError(new ApiError("Private server diagnostic", status));
  expect(message).not.toContain("Private server diagnostic");
  expect(message).not.toBe("Zahtev nije uspeo. Proveri vezu i pokušaj ponovo.");
});
it("preserves the server retry duration in localized rate-limit feedback", () => {
  expect(accountAccessError(new ApiError("Too many requests", 429, 45))).toContain("45 sekundi");
});
it("does not expose arbitrary network exceptions", () => {
  expect(accountAccessError(new Error("sensitive internal URL"))).toBe("Zahtev nije uspeo. Proveri vezu i pokušaj ponovo.");
});
