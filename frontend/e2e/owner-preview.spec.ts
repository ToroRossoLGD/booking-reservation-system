import { expect, test } from "@playwright/test";

test("owner previews a private draft with protected photos on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => localStorage.setItem("bookica_token", "preview-test"));
  const requests: string[] = [];
  page.on("request", request => { if (request.url().includes("/api/")) requests.push(request.method() + " " + new URL(request.url()).pathname); });
  await page.route("**/api/owner/properties/7", route => {
    expect(route.request().headers().authorization).toBe("Bearer preview-test");
    return route.fulfill({ json: { id: 7, venue_id: 1, title: "Nacrt sa terasom", description: "Svetao stan sa prostranom terasom.", city: "Beograd", offer_type: "long_term", area_sqm: 50, rooms: 2, price_cents: 65000, currency: "EUR", contact_email: "owner@example.com", is_published: false, deposit_cents: 0 } });
  });
  await page.route("**/api/owner/properties/7/photos", route => route.fulfill({ json: [{ id: 1, property_id: 7, position: 0, width: 600, height: 400 }] }));
  await page.route("**/api/owner/properties/7/photos/1/image?thumbnail=true", route => {
    expect(route.request().headers().authorization).toBe("Bearer preview-test");
    return route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400"><rect width="600" height="400" fill="#396b55"/></svg>' });
  });
  await page.goto("/owner/properties/7/preview");
  await expect(page.getByRole("heading", { name: "Nacrt sa terasom" })).toBeVisible();
  await expect(page.getByText(/Nacrt — nije u javnoj ponudi/)).toBeVisible();
  await expect(page.getByRole("img", { name: "Fotografija 1" })).toBeVisible();
  await expect(page.getByText("Depozit: Bez depozita")).toBeVisible();
  expect(requests.every(request => request.startsWith("GET /api/owner/properties/"))).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
