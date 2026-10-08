import { expect, test } from "./fixtures";

test("saved search survives reload and reopens its filters on page one", async ({ page }, testInfo) => {
  const requests: URLSearchParams[] = [];
  await page.route("**/api/properties?*", route => {
    const params = new URL(route.request().url()).searchParams;
    requests.push(params);
    return route.fulfill({ json: { items: [], total: 0, offset: Number(params.get("offset")), limit: 12, has_next: false } });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?city=Novi+Sad&offer_type=long_term&currency=EUR&max_price_cents=75000&rooms=0&offset=12");
  await page.getByLabel("Naziv pretrage").fill("Garsonjera do 750 EUR");
  await page.getByRole("button", { name: "Sačuvaj trenutnu pretragu" }).click();
  await expect(page.getByRole("link", { name: "Garsonjera do 750 EUR" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("region", { name: "Sačuvane pretrage" }).screenshot({ path: testInfo.outputPath("saved-search-mobile.png") });
  await page.reload();
  await page.getByRole("button", { name: "Obriši filtere" }).click();
  await page.getByRole("link", { name: "Garsonjera do 750 EUR" }).click();
  await expect(page.getByPlaceholder("Grad ili destinacija")).toHaveValue("Novi Sad");
  await expect(page.getByText("Nema oglasa za ovaj izbor.")).toBeVisible();
  expect(new URL(page.url()).searchParams.has("offset")).toBe(false);
  expect(requests.at(-1)?.get("rooms")).toBe("0");
  expect(requests.at(-1)?.get("max_price_cents")).toBe("75000");
  expect(requests.at(-1)?.get("offer_type")).toBe("long_term");
  await page.getByRole("button", { name: "Ukloni pretragu: Garsonjera do 750 EUR" }).click();
  await page.reload();
  await expect(page.getByRole("link", { name: "Garsonjera do 750 EUR" })).toHaveCount(0);
});
