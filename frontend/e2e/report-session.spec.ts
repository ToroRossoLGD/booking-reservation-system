import { expect, test } from "./fixtures";

for (const mobile of [false, true]) {
  test(`report drafts follow the account on ${mobile ? "mobile" : "desktop"}`, async ({ page, context }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/properties/7", route => route.fulfill({ json: { id: 7, venue_id: 1, title: "Stan", city: "Novi Sad", description: "Stan sa terasom.", offer_type: "long_term", area_sqm: 60, rooms: 2, price_cents: 65000, currency: "EUR", is_published: true } }));
    let release!: () => void;
    const pending = new Promise<void>(resolve => { release = resolve; });
    const requests: Array<{ token: string; id: string }> = [];
    await page.route("**/api/properties/7/reports", async route => {
      requests.push({ token: route.request().headers().authorization, id: route.request().postDataJSON().request_id });
      if (requests.length === 1) await pending;
      await route.fulfill({ status: 201, json: { id: requests.length } });
    });
    await page.goto("/properties/7");
    const other = await context.newPage();
    await other.goto("/help");
    await other.evaluate(() => localStorage.setItem("bookica_token", "first"));
    const trigger = page.getByRole("button", { name: "Prijavi oglas", exact: true });
    const description = page.getByLabel("Opis problema");
    await trigger.click();
    await description.fill("Privatna prijava prvog korisnika.");
    const started = page.waitForRequest("**/api/properties/7/reports");
    await page.getByRole("button", { name: "Pošalji prijavu" }).click();
    await started;
    await other.evaluate(() => localStorage.setItem("bookica_token", "second"));
    await expect(trigger).toHaveAttribute("aria-expanded", "false");
    await expect(trigger).toBeEnabled();
    await trigger.click();
    await expect(description).toHaveValue("");
    const response = page.waitForResponse("**/api/properties/7/reports");
    release();
    await response;
    await expect(description).toBeVisible();
    await expect(page.getByText("Prijava je poslata administratoru.", { exact: false })).toHaveCount(0);
    await description.fill("Prijava novog korisnika za isti oglas.");
    await page.getByRole("button", { name: "Pošalji prijavu" }).click();
    await expect(page.getByRole("status")).toContainText("Prijava je poslata");
    expect(requests.map(request => request.token)).toEqual(["Bearer first", "Bearer second"]);
    expect(requests[0].id).not.toBe(requests[1].id);
    await other.evaluate(() => localStorage.removeItem("bookica_token"));
    await expect(trigger).toHaveAttribute("aria-expanded", "false");
    await trigger.click();
    await expect(description).toHaveValue("");
    expect(requests).toHaveLength(2);
  });
}
