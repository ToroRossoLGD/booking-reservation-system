import { expect, it } from "vitest";
import { notificationLinkLabel } from "./notification-link";

it("permits known account destinations and strictly internal listing URLs", () => {
  expect(notificationLinkLabel("/owner/stays")).toBe("Rezervacije tvojih stanova");
  expect(notificationLinkLabel("/properties/7")).toBe("Pogledaj oglas");
  expect(notificationLinkLabel("/properties/7?check_in=2030-10-01&check_out=2030-10-04&guests=2")).toBe("Pogledaj oglas");
  for (const value of [null, "//evil.example", "https://evil.example", "javascript:alert(1)", "/properties/0", "/properties/7/extra", "/properties/9007199254740992", "/properties/7?next=https://evil.example", "/properties/7?check_in=bad", "/properties/7#evil"]) expect(notificationLinkLabel(value)).toBeNull();
});
