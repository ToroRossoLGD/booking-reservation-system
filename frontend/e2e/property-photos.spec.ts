import { expect, test } from "@playwright/test";
import type { PropertyPhoto } from "../src/property-types";

for (const mobile of [false, true]) {
  test(`owner uploads and manages gallery on ${mobile ? "mobile" : "desktop"}`, async ({ page }, testInfo) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => localStorage.setItem("bookica_token", "photo-test"));
    let photos: PropertyPhoto[] = [];
    let nextId = 1;
    const listing = { id: 7, venue_id: 1, title: "Stan sa terasom", description: "Svetao stan u centru grada sa prostranom terasom.", city: "Beograd", offer_type: "long_term", area_sqm: 50, rooms: 2, price_cents: 65000, currency: "EUR", contact_email: "owner@example.com", is_published: true };
    await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 1, email: "owner@example.com", role: "owner" } }));
    await page.route("**/api/venues", route => route.fulfill({ json: [] }));
    await page.route("**/api/promotions/active", route => route.fulfill({ json: [] }));
    await page.route("**/api/owner/stats", route => route.fulfill({ json: { total_venues: 1, total_resources: 0, total_reservations: 0, total_revenue_cents: 0, reservations_by_status: {}, top_resources: [] } }));
    await page.route("**/api/owner/venues", route => route.fulfill({ json: [{ id: 1, name: "Moj objekat", address: "Centar", description: null, owner_id: 1 }] }));
    await page.route("**/api/owner/resources", route => route.fulfill({ json: [] }));
    await page.route("**/api/owner/reservations", route => route.fulfill({ json: [] }));
    const list = () => ({ items: [{ ...listing, photos }], total: 1, limit: 20, offset: 0, has_next: false });
    await page.route("**/api/owner/properties?*", route => route.fulfill({ json: list() }));
    await page.route("**/api/properties?*", route => route.fulfill({ json: list() }));
    await page.route("**/api/favorites/properties/status?*", route => route.fulfill({ json: { property_ids: [] } }));
    await page.route("**/api/owner/properties/7/photos", route => {
      if (route.request().method() === "POST") {
        expect(route.request().headers().authorization).toBe("Bearer photo-test");
        expect(route.request().headers()["content-type"]).toContain("multipart/form-data");
        const photo = { id: nextId++, property_id: 7, position: photos.length, width: 640, height: 400 };
        photos.push(photo);
        return route.fulfill({ status: 201, json: photo });
      }
      return route.fulfill({ json: photos });
    });
    await page.route("**/api/owner/properties/7/photos/order", route => {
      const ids: number[] = route.request().postDataJSON().photo_ids;
      photos = ids.map((id, position) => ({ ...photos.find(photo => photo.id === id)!, position }));
      return route.fulfill({ json: photos });
    });
    await page.route(/\/api\/owner\/properties\/7\/photos\/\d+$/, route => {
      const id = Number(route.request().url().split("/").at(-1));
      photos = photos.filter(photo => photo.id !== id);
      return route.fulfill({ status: 204 });
    });
    await page.goto("/owner");
    const fixture = Buffer.from(await page.evaluate(() => {
      const canvas = document.createElement("canvas"); canvas.width = 640; canvas.height = 400;
      const ctx = canvas.getContext("2d")!; ctx.fillStyle = "#d8daca"; ctx.fillRect(0, 0, 640, 400); ctx.fillStyle = "#496b64"; ctx.fillRect(80, 60, 220, 230); ctx.fillStyle = "#eee9df"; ctx.fillRect(330, 160, 250, 150);
      return canvas.toDataURL("image/png").split(",")[1];
    }), "base64");
    await page.route(/\/api\/(owner\/)?properties\/7\/photos\/\d+\/image\?/, route => route.fulfill({ contentType: "image/png", body: fixture }));
    await page.getByRole("button", { name: "Fotografije: Stan sa terasom" }).click();
    await page.getByLabel("Dodaj fotografije").setInputFiles([{ name: "living-room.png", mimeType: "image/png", buffer: fixture }, { name: "terrace.png", mimeType: "image/png", buffer: fixture }]);
    await page.getByRole("button", { name: "Otpremi fotografije (2)" }).click();
    await expect(page.getByText("Dodato fotografija: 2.")).toBeVisible();
    await page.getByRole("button", { name: "Postavi fotografiju 2 kao naslovnu" }).click();
    await expect(page.getByText("Redosled je sačuvan. Prva fotografija je naslovna.")).toBeVisible();
    expect(photos[0].id).toBe(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("owner-photos.png"), fullPage: true });
    await page.goto("/");
    const cover = page.getByRole("button", { name: "Otvori galeriju: Stan sa terasom" });
    await expect(cover.getByRole("img")).toHaveAttribute("src", /\/photos\/2\/image/);
    await cover.click();
    const dialog = page.getByRole("dialog", { name: "Galerija: Stan sa terasom" });
    await expect(dialog).toBeVisible();
    await page.getByRole("button", { name: "Sledeća fotografija" }).click();
    await expect(dialog.getByRole("status")).toHaveText("2 / 2");
    await page.keyboard.press("ArrowLeft");
    await expect(dialog.getByRole("status")).toHaveText("1 / 2");
    const bounds = await dialog.boundingBox();
    expect(bounds?.x).toBe(0); expect(bounds?.y).toBe(0);
    expect(bounds?.width).toBe(await page.evaluate(() => innerWidth));
    expect(bounds?.height).toBe(await page.evaluate(() => innerHeight));
    await page.screenshot({ path: testInfo.outputPath("public-gallery.png") });
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
    await expect(cover).toBeFocused();
    await page.goto("/owner");
    await page.getByRole("button", { name: "Fotografije: Stan sa terasom" }).click();
    await page.getByRole("button", { name: "Obriši fotografiju 1" }).click();
    await page.getByRole("button", { name: "Potvrdi brisanje" }).click();
    await expect(page.getByText("Fotografija je uklonjena.")).toBeVisible();
    expect(photos.map(photo => photo.id)).toEqual([1]);
  });
}
