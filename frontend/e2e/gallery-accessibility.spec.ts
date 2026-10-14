import { expect, test } from "./fixtures";

const listing = { id: 7, venue_id: 1, title: "Stan sa terasom", description: "Svetao stan u centru.", city: "Beograd", offer_type: "sale", area_sqm: 50, rooms: 2, price_cents: 10000000, currency: "EUR", contact_email: "owner@example.com", is_published: true };
const photos = [1, 2, 3].map((id, position) => ({ id, position, property_id: 7, width: 1, height: 1 }));
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=", "base64");

test.beforeEach(async ({ page }) => {
  await page.route("**/api/properties/7", route => route.fulfill({ json: { ...listing, photos } }));
  await page.route(/\/api\/properties\/7\/photos\/\d+\/image\?/, route => route.fulfill({ contentType: "image/png", body: png }));
});

for (const mobile of [false, true]) {
  test(`gallery keyboard navigation and focus restoration on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 664 });
    await page.goto("/properties/7");
    const opener = page.getByRole("button", { name: "Otvori galeriju: Stan sa terasom" });
    await opener.click();
    const dialog = page.getByRole("dialog", { name: "Galerija: Stan sa terasom" });
    const close = dialog.getByRole("button", { name: "Zatvori galeriju" });
    await expect(close).toBeFocused();
    await page.keyboard.press("Shift+Tab");
    await expect(dialog.getByRole("button", { name: "Prikaži fotografiju 3" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(close).toBeFocused();
    await page.keyboard.press("ArrowLeft");
    await expect(dialog.getByRole("status")).toHaveText("3 / 3");
    await page.keyboard.press("ArrowRight");
    await expect(dialog.getByRole("status")).toHaveText("1 / 3");
    await page.keyboard.press("End");
    await expect(dialog.getByRole("status")).toHaveText("3 / 3");
    await page.keyboard.press("Home");
    await expect(dialog.getByRole("status")).toHaveText("1 / 3");
    await opener.evaluate(element => element.focus());
    await expect(close).toBeFocused();
    expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(opener).toBeFocused();
    expect(await page.evaluate(() => document.body.style.overflow)).not.toBe("hidden");
    await opener.click();
    await close.click();
    await expect(opener).toBeFocused();
  });
}

test("single-photo error recovery keeps focus inside the gallery", async ({ page }) => {
  await page.route("**/api/properties/7", route => route.fulfill({ json: { ...listing, photos: photos.slice(0, 1) } }));
  await page.route("**/api/properties/7/photos/1/image?thumbnail=false", route => route.abort(), { times: 1 });
  await page.goto("/properties/7");
  await page.getByRole("button", { name: "Otvori galeriju: Stan sa terasom" }).click();
  const dialog = page.getByRole("dialog", { name: "Galerija: Stan sa terasom" });
  await expect(dialog.getByRole("button", { name: "Prethodna fotografija" })).toBeDisabled();
  await expect(dialog.getByRole("button", { name: "Sledeća fotografija" })).toBeDisabled();
  await dialog.getByRole("button", { name: "Pokušaj ponovo" }).click();
  await expect(dialog.getByRole("button", { name: "Zatvori galeriju" })).toBeFocused();
  await expect(dialog.getByRole("img", { name: "Stan sa terasom — fotografija 1" })).toBeVisible();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.getByRole("button", { name: "Prikaži fotografiju 1" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});
