import { expect, test } from "@playwright/test";
import type { ModerationCase, PropertyReport } from "../src/moderation-types";

test("report, admin suspension, owner appeal and restoration keep publication explicit", async ({ browser, baseURL }, testInfo) => {
  const property = { id: 7, venue_id: 1, title: "Stan pored reke", city: "Novi Sad", description: "Svetao stan sa terasom blizu reke.", offer_type: "sale", area_sqm: 60, rooms: 2, price_cents: 14000000, currency: "EUR", contact_email: "owner@example.com", is_published: true };
  const listing: ModerationCase = { id: 7, title: property.title, state: "clear", version: 0, note: "", appeal: "", is_published: true };
  let report: PropertyReport | null = null;
  const customer = await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } });
  const owner = await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } });
  const admin = await browser.newContext({ baseURL });
  try {
    for (const [context, role, id] of [[customer, "customer", 2], [owner, "owner", 1], [admin, "admin", 4]] as const) {
      await context.addInitScript(() => localStorage.setItem("bookica_token", "test-member"));
      await context.route("**/api/auth/me", route => route.fulfill({ json: { id, role, email: `${role}@example.com` } }));
      await context.route("**/api/favorites/properties/status?*", route => route.fulfill({ json: { property_ids: [] } }));
      await context.route("**/api/properties/7", route => listing.is_published ? route.fulfill({ json: property }) : route.fulfill({ status: 404, json: { detail: "Listing not found" } }));
      await context.route("**/api/properties/7/reports", route => {
        const body = route.request().postDataJSON();
        expect(role).toBe("customer"); expect(body.request_id).toBeTruthy();
        report = { id: 1, property_id: 7, category: body.category, details: body.details, status: "pending", listing: { ...listing }, created_at: "2026-10-03T08:00:00Z", resolved_at: null, snapshot: { ...property } };
        return route.fulfill({ status: 201, json: report });
      });
      await context.route("**/api/property-reports/mine?*", route => route.fulfill({ json: { items: role === "customer" && report ? [{ ...report, listing: { ...listing, note: "", appeal: "" } }] : [], total: role === "customer" && report ? 1 : 0, has_next: false } }));
      await context.route("**/api/admin/property-reports?*", route => {
        const items = report?.status === new URL(route.request().url()).searchParams.get("status") ? [{ ...report, listing }] : [];
        return route.fulfill({ json: { items, total: items.length, has_next: false } });
      });
      await context.route(/\/api\/(admin|owner)\/property-moderation\?/, route => route.fulfill({ json: { items: listing.version ? [listing] : [], total: listing.version ? 1 : 0, has_next: false } }));
      await context.route(/\/api\/(admin\/properties\/7\/reports\/1\/decision|properties\/7\/moderation)$/, route => {
        const body = route.request().postDataJSON();
        expect(body.version).toBe(listing.version);
        expect(body.request_id).toBeTruthy();
        if (body.action === "hide") { expect(role).toBe("admin"); listing.state = "suspended"; listing.note = body.note; listing.is_published = false; report!.status = "action_taken"; }
        else if (body.action === "appeal") { expect(role).toBe("owner"); listing.state = "appealed"; listing.appeal = body.note; }
        else { expect(role).toBe("admin"); expect(body.action).toBe("restore"); listing.state = "clear"; listing.note = body.note; }
        listing.version++;
        return route.fulfill({ json: listing });
      });
    }
    const guestPage = await customer.newPage();
    await guestPage.goto("/properties/7");
    await guestPage.getByRole("button", { name: "Prijavi oglas" }).click();
    await guestPage.getByLabel("Opis problema").fill("Fotografije i adresa ne odgovaraju opisu.");
    await guestPage.getByRole("button", { name: "Pošalji prijavu" }).click();
    await expect(guestPage.getByText("Prijava je poslata administratoru.")).toBeVisible();
    const adminPage = await admin.newPage();
    await adminPage.goto("/moderation");
    await adminPage.getByLabel("Radnja").selectOption("hide");
    await adminPage.getByLabel("Obrazloženje za vlasnika i administraciju").fill("Ispravite netačan opis i fotografije.");
    await adminPage.getByRole("button", { name: "Suspenduj oglas" }).click();
    await expect(adminPage.getByText("Nema stavki za prikaz.")).toBeVisible();
    await guestPage.reload();
    await expect(guestPage.getByRole("heading", { name: "Oglas nije dostupan." })).toBeVisible();
    const ownerPage = await owner.newPage();
    await ownerPage.goto("/moderation");
    await ownerPage.getByRole("button", { name: "Odluke o mojim oglasima" }).click();
    await expect(ownerPage.getByText(/Obrazloženje administratora/)).toBeVisible();
    await expect(ownerPage.getByText("Fotografije i adresa ne odgovaraju opisu.")).toHaveCount(0);
    await ownerPage.getByLabel("Obrazloženje za vlasnika i administraciju").fill("Opis je ispravljen; molim ponovni pregled.");
    await ownerPage.getByRole("button", { name: "Zatraži ponovni pregled" }).click();
    await expect(ownerPage.getByText("Čeka ponovni pregled", { exact: true })).toBeVisible();
    expect(await ownerPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await ownerPage.screenshot({ path: testInfo.outputPath("owner-moderation-mobile.png"), fullPage: true });
    await adminPage.getByRole("button", { name: "Odluke i zahtevi vlasnika" }).click();
    await adminPage.getByLabel("Obrazloženje za vlasnika i administraciju").fill("Ispravke su proverene, možete objaviti nacrt.");
    await adminPage.getByRole("button", { name: "Ukini zabranu objavljivanja" }).click();
    await expect(adminPage.getByText(/Zabrana objavljivanja je ukinuta/)).toBeVisible();
    expect(listing.is_published).toBe(false);
    await guestPage.reload();
    await expect(guestPage.getByRole("heading", { name: "Oglas nije dostupan." })).toBeVisible();
  } finally { await customer.close(); await owner.close(); await admin.close(); }
});
