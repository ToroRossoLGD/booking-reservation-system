import { expect, test } from "./fixtures";

for (const mobile of [false, true]) {
  test(`customer guide is discoverable and usable on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 664 });
    await page.route("**/api/properties?*", route => route.fulfill({ json: { items: [], total: 0, limit: 12, offset: 0, has_next: false } }));
    await page.goto("/");
    await page.getByRole("link", { name: "Kako funkcioniše Bookica?", exact: true }).click();
    await expect(page).toHaveURL(/\/help$/);
    await expect(page).toHaveTitle("Kako funkcioniše Bookica | Bookica");
    await expect(page.getByRole("main")).toHaveCount(1);
    await expect(page.getByText("Plaćanje je na licu mesta.", { exact: true })).toBeVisible();
    const question = page.getByText("Kako otkazujem ili menjam datume?", { exact: true });
    await question.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByText(/Stara rezervacija ostaje aktivna/)).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(page.getByText(/Stara rezervacija ostaje aktivna/)).not.toBeVisible();
    await page.getByRole("link", { name: "Najam i kupovina", exact: true }).click();
    await page.getByText("Da li slanjem upita rezervišem stan?", { exact: true }).click();
    await expect(page.getByText(/Upit otvara razgovor/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Moji upiti za najam", exact: true })).toHaveAttribute("href", "/rentals");
    await expect(page.getByRole("link", { name: "Moji upiti za kupovinu", exact: true })).toHaveAttribute("href", "/sales");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole("link", { name: "Nazad na ponudu nekretnina" }).click();
    await expect(page.getByRole("heading", { name: /negde te čeka/i })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test("guide supports a direct trailing-slash link, skip navigation and account recovery", async ({ page }) => {
  await page.goto("/help/");
  await expect(page.getByRole("heading", { name: "Kako funkcioniše Bookica?", exact: true })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Preskoči na sadržaj" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await page.getByText("Ne mogu da pristupim nalogu ili da potvrdim email", { exact: true }).click();
  await page.getByRole("link", { name: "Obnovi lozinku" }).click();
  await expect(page).toHaveURL(/\/forgot-password$/);
  await expect(page.getByLabel("Email adresa")).toBeVisible();
});
