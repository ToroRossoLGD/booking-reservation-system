import { expect, test } from "./fixtures";

for (const mobile of [false, true]) {
  test(`listing share recovery on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async () => { throw new Error("denied"); } } });
      Object.defineProperty(navigator, "share", { configurable: true, value: async () => { throw new DOMException("cancelled", "AbortError"); } });
    });
    await page.route("**/api/properties/7", route => route.fulfill({ json: { id: 7, venue_id: 1, title: "Stan pored reke", city: "Novi Sad", description: "Stan sa terasom.", offer_type: "long_term", area_sqm: 60, rooms: 2, price_cents: 65000, currency: "EUR", is_published: true } }));
    await page.goto("/properties/7?private=omit#secret");
    const share = page.getByRole("button", { name: "Podeli oglas", exact: true });
    await share.click();
    await expect(share).toBeEnabled();
    await expect(page.getByRole("alert")).toHaveCount(0);
    const copy = page.getByRole("button", { name: "Kopiraj link oglasa" });
    const manual = page.getByLabel("Kopiraj adresu ručno");
    for (let attempt = 0; attempt < 2; attempt++) {
      await copy.click();
      await expect(manual).toBeFocused();
      await expect(manual).toHaveValue("http://127.0.0.1:4173/properties/7");
      await expect(manual).toHaveAccessibleDescription(/Deljenje nije uspelo/);
      expect(await manual.evaluate((input: HTMLInputElement) => input.selectionStart === 0 && input.selectionEnd === input.value.length)).toBe(true);
    }
    await page.evaluate(() => Object.defineProperty(navigator, "share", { value: async () => { throw new Error("unavailable"); } }));
    await share.click();
    await expect(manual).toBeFocused();
    await page.evaluate(() => Object.defineProperty(navigator, "clipboard", { value: { writeText: async () => {} } }));
    await copy.click();
    await expect(page.getByRole("status")).toHaveText("Link je kopiran.");
    await expect(manual).toHaveCount(0);
    await expect(page.getByRole("alert")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
