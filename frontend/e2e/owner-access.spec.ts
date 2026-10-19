import { expect, test } from "./fixtures";

for (const admin of [false, true]) {
  for (const mobile of [false, true]) {
    test(`owner request pagination recovery ${admin ? "admin" : "customer"} ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
      if (mobile) await page.setViewportSize({ width: 390, height: 844 });
      let empty = false;
      let fail = false;
      const offsets: number[] = [];
      await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 1, email: "member@example.com", role: admin ? "admin" : "customer", email_verified: true } }));
      await page.route(admin ? "**/api/admin/owner-access?*" : "**/api/owner-access/mine?*", route => {
        const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
        offsets.push(offset);
        if (fail) return route.fulfill({ status: 503, json: { detail: "unavailable" } });
        return route.fulfill({ json: {
          items: empty ? [] : [{ id: offset + 1, user_id: 1, email: "member@example.com", details: "Upravljam porodičnim stanom na Zlatiboru.", status: "pending", created_at: "2026-10-17T10:00:00Z", decided_at: null, decision_note: null }],
          has_next: !empty && offset === 0,
        } });
      });
      await page.goto(admin ? "/admin/owner-access" : "/owner-access");
      const heading = page.getByRole("heading", { name: admin ? "Pregled zahteva" : "Istorija tvojih zahteva" });
      await page.getByRole("button", { name: "Sledeća", exact: true }).click();
      await expect(page.getByText("Stranica 2", { exact: true })).toBeVisible();
      await expect(heading).toBeFocused();
      await page.getByRole("button", { name: "Prethodna", exact: true }).click();
      await expect(page.getByText("Stranica 1", { exact: true })).toBeVisible();
      await expect(heading).toBeFocused();
      await page.getByRole("button", { name: "Sledeća", exact: true }).click();
      await expect(page.getByText("Stranica 2", { exact: true })).toBeVisible();
      fail = true;
      await page.getByRole("button", { name: "Osveži zahteve" }).click();
      await expect(page.getByRole("alert")).toContainText("Zahtev nije potvrđen");
      expect(offsets.at(-1)).toBe(20);
      fail = false;
      empty = true;
      await page.getByRole("button", { name: "Osveži zahteve" }).click();
      await expect(page.getByText("Stranica 1", { exact: true })).toBeVisible();
      await expect(page.getByText("Nema zahteva za prikaz.")).toBeVisible();
      await expect(page.getByRole("status")).toContainText("Prikazana je prva stranica");
      await expect(heading).toBeFocused();
      await expect(page.getByRole("button", { name: "Prethodna", exact: true })).toBeDisabled();
      await expect(page.getByRole("button", { name: "Sledeća", exact: true })).toBeDisabled();
      expect(offsets).toEqual([0, 20, 0, 20, 20, 20, 0]);
    });
  }
}

for (const mobile of [false, true]) {
  test(`customer request and admin decision on ${mobile ? "mobile" : "desktop"}`, async ({ page }, testInfo) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    let role = "customer";
    let verified = false;
    let expired = false;
    let requests: Array<{ id: number; user_id: number; email: string; details: string; status: string; created_at: string; decided_at: string | null; decision_note: string | null }> = [];
    let creates = 0;
    let decisions = 0;
    let firstId = "";
    await page.route("**/api/auth/me", route => expired ? route.fulfill({ status: 401, json: { detail: "expired" } }) : route.fulfill({ json: { id: role === "admin" ? 3 : 1, email: "member@example.com", role, email_verified: verified } }));
    await page.route("**/api/owner-access/mine?*", route => route.fulfill({ json: { items: requests, has_next: false } }));
    await page.route("**/api/admin/owner-access?*", route => {
      const status = new URL(route.request().url()).searchParams.get("status");
      return route.fulfill({ json: { items: requests.filter(item => item.status === status), has_next: false } });
    });
    await page.route("**/api/owner-access/requests", route => {
      creates++;
      const data = route.request().postDataJSON();
      if (!firstId) firstId = data.request_id;
      expect(data.request_id).toBe(firstId);
      if (creates === 1) return route.fulfill({ status: 503, json: { detail: "unavailable" } });
      requests = [{ id: 7, user_id: 1, email: "member@example.com", details: data.details, status: "pending", created_at: "2026-10-17T10:00:00Z", decided_at: null, decision_note: null }];
      return route.fulfill({ status: 201, json: requests[0] });
    });
    await page.route("**/api/admin/owner-access/7/decision", route => {
      decisions++;
      const data = route.request().postDataJSON();
      if (decisions === 1) return route.fulfill({ status: 503, json: { detail: "unavailable" } });
      requests[0] = { ...requests[0], status: data.action, decision_note: data.note, decided_at: "2026-10-17T11:00:00Z" };
      return route.fulfill({ json: requests[0] });
    });
    await page.goto("/owner-access");
    await expect(page.getByRole("link", { name: "Potvrdi email adresu" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Pošalji zahtev" })).toHaveCount(0);
    verified = true;
    await page.getByRole("button", { name: "Osveži zahteve" }).click();
    const description = page.getByLabel("Opis planiranih oglasa");
    const submit = page.getByRole("button", { name: "Pošalji zahtev" });
    for (const invalid of ["", "     ", "Kratak opis", "a".repeat(2001)]) {
      await description.fill(invalid);
      await submit.click();
      await expect(description).toBeFocused();
      await expect(description).toHaveAttribute("aria-invalid", "true");
      await expect(description).toHaveAccessibleDescription(/Unesi opis od 20 do 2000/);
      expect(creates).toBe(0);
    }
    await description.fill("  " + "🏠".repeat(20) + "  ");
    await expect(description).toHaveAttribute("aria-invalid", "false");
    await expect(page.getByText("Broj znakova: 20 / 2000", { exact: true })).toBeVisible();
    await page.getByLabel("Opis planiranih oglasa").fill("Upravljam porodičnim stanom na Zlatiboru za kratke boravke.");
    await page.getByRole("button", { name: "Pošalji zahtev" }).click();
    await expect(page.getByRole("alert")).toContainText("Zahtev nije potvrđen");
    await expect(page.getByLabel("Opis planiranih oglasa")).toHaveValue(/Zlatiboru/);
    await page.getByRole("button", { name: "Pošalji zahtev" }).click();
    await expect(page.getByRole("heading", { name: "Zahtev #7 — Na čekanju" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Pošalji zahtev" })).toHaveCount(0);
    await page.goto("/admin/owner-access");
    await expect(page.getByRole("alert")).toContainText("samo administratoru");
    role = "admin";
    await page.getByRole("button", { name: "Osveži zahteve" }).click();
    const note = page.getByLabel("Obrazloženje za korisnika");
    for (const action of ["Odobri pristup", "Odbij zahtev"]) {
      for (const invalid of ["", "   ", "Kratko", "a".repeat(2001)]) {
        await note.fill(invalid);
        await page.getByRole("button", { name: action, exact: true }).click();
        await expect(note).toBeFocused();
        await expect(note).toHaveAttribute("aria-invalid", "true");
        await expect(note).toHaveAccessibleDescription(/Unesi obrazloženje od 10 do 2000/);
        await expect(page.getByRole("button", { name: "Potvrdi odluku" })).toHaveCount(0);
        expect(decisions).toBe(0);
      }
    }
    await note.fill("  " + "🏠".repeat(10) + "  ");
    await expect(note).toHaveAttribute("aria-invalid", "false");
    await expect(note).toHaveAccessibleDescription(/Broj znakova: 10 \/ 2000/);
    await page.getByLabel("Obrazloženje za korisnika").fill("Provereno ovlašćenje za oglašavanje porodičnog stana.");
    await page.getByRole("button", { name: "Odobri pristup" }).click();
    await expect(page.getByText(/poništava sve postojeće sesije/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Odustani", exact: true })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: "Odobri pristup" })).toBeFocused();
    await page.getByRole("button", { name: "Odbij zahtev" }).click();
    await expect(page.getByRole("button", { name: "Odustani", exact: true })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: "Odbij zahtev" })).toBeFocused();
    expect(decisions).toBe(0);
    await page.getByRole("button", { name: "Odobri pristup" }).click();
    await page.getByRole("button", { name: "Potvrdi odluku" }).click();
    await expect(page.getByRole("alert")).toContainText("Zahtev nije potvrđen");
    await expect(note).toHaveValue("Provereno ovlašćenje za oglašavanje porodičnog stana.");
    await page.getByRole("button", { name: "Potvrdi odluku" }).click();
    await expect(page.getByText("Nema zahteva za prikaz.")).toBeVisible();
    await page.getByLabel("Status zahteva").selectOption("approved");
    await expect(page.getByRole("heading", { name: "Zahtev #7 — Odobren" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("owner-access-admin.png"), fullPage: true });
    expect(decisions).toBe(2);
    expired = true;
    await page.goto("/owner-access");
    await expect(page.getByRole("alert")).toContainText("Prijavi se ponovo");
    expired = false; role = "owner";
    await page.getByRole("button", { name: "Osveži zahteve" }).click();
    await expect(page.getByRole("link", { name: "Otvori vlasnički panel" })).toHaveAttribute("href", "/owner");
    await expect(page.getByText("Provereno ovlašćenje za oglašavanje porodičnog stana.", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
