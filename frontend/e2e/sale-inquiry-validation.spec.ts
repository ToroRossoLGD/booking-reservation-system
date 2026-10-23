import { expect, test } from "./fixtures";

for (const mobile of [false, true]) {
  test(`sale inquiry guidance on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/properties/7", route => route.fulfill({ json: { id: 7, venue_id: 1, title: "Stan za prodaju", city: "Novi Sad", description: "Stan sa terasom.", offer_type: "sale", area_sqm: 60, rooms: 2, price_cents: 12000000, currency: "EUR", is_published: true } }));
    const requests: Array<{ message: string; request_id: string }> = [];
    await page.route("**/api/properties/7/sale-inquiries", route => {
      requests.push(route.request().postDataJSON());
      return requests.length === 1 ? route.fulfill({ status: 503, json: { detail: "unavailable" } }) : route.fulfill({ status: 201, json: { id: 1 } });
    });
    await page.goto("/properties/7");
    const message = page.getByLabel("Poruka prodavcu");
    const submit = page.getByRole("button", { name: "Pošalji upit za kupovinu" });
    for (const value of ["", "   ", "Kratko", "a".repeat(3001)]) {
      await message.fill(value);
      await submit.click();
      await expect(message).toBeFocused();
      await expect(message).toHaveAttribute("aria-invalid", "true");
      await expect(message).toHaveAccessibleDescription(/Unesi poruku od 10 do 3000/);
      expect(requests).toHaveLength(0);
    }
    await message.fill("  " + "🏠".repeat(10) + "  ");
    await expect(message).toHaveAccessibleDescription(/Uneto: 10\/3000/);
    await expect(message).toHaveAttribute("aria-invalid", "false");
    await message.fill("  Zanima me razgledanje ovog stana.  ");
    await submit.click();
    await expect(page.getByRole("alert")).toContainText("Potvrda nije stigla");
    await expect(message).toHaveValue("  Zanima me razgledanje ovog stana.  ");
    await submit.click();
    await expect(page.getByRole("status")).toBeFocused();
    await expect(page.getByRole("status")).toContainText("Upit za kupovinu je poslat");
    expect(requests).toHaveLength(2);
    expect(requests[0]).toEqual(requests[1]);
    expect(requests[0].message).toBe("Zanima me razgledanje ovog stana.");
  });
}
