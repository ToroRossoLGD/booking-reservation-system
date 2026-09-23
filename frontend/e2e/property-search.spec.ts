import { expect, test } from "@playwright/test";

test("advanced filters serialize prices, survive pagination and reset on mobile", async ({ page }, testInfo) => {
  const requests: URLSearchParams[] = [];
  await page.route("**/api/properties?*", route => {
    const params = new URL(route.request().url()).searchParams;
    requests.push(params);
    return route.fulfill({ json: { items: [], total: 13, limit: 12, offset: Number(params.get("offset")), has_next: params.get("offset") === "0" } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Dugoročni najam", exact: true }).click();
  await page.getByText("Napredni filteri i sortiranje").click();
  await page.getByLabel("Cena od", { exact: true }).fill("500.25");
  await page.getByLabel("Cena do", { exact: true }).fill("750");
  await page.getByLabel("Valuta").selectOption("USD");
  await page.getByLabel("Broj soba").fill("0");
  await page.getByLabel("Sortiranje").selectOption("price_asc");
  await page.getByRole("button", { name: "Primeni filtere" }).click();
  await expect.poll(() => requests.at(-1)?.get("min_price_cents")).toBe("50025");
  expect(requests.at(-1)?.get("max_price_cents")).toBe("75000");
  expect(requests.at(-1)?.get("rooms")).toBe("0");
  expect(requests.at(-1)?.get("currency")).toBe("USD");
  await page.getByRole("button", { name: "Sledeća" }).click();
  await expect.poll(() => requests.at(-1)?.get("offset")).toBe("12");
  expect(requests.at(-1)?.get("min_price_cents")).toBe("50025");
  expect(requests.at(-1)?.get("sort")).toBe("price_asc");
  await page.getByLabel("Kvadratura od (m²)").fill("25");
  await page.getByRole("button", { name: "Primeni filtere" }).click();
  await expect.poll(() => requests.at(-1)?.get("offset")).toBe("0");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByLabel("Cena od", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("search-filters-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "Obriši filtere" }).click();
  await expect.poll(() => requests.at(-1)?.has("min_price_cents")).toBe(false);
  expect(requests.at(-1)?.has("rooms")).toBe(false);
  expect(requests.at(-1)?.has("offer_type")).toBe(false);
});
