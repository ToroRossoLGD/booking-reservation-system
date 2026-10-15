export type ApplicationRoute = {
  page: "home" | "account" | "owner";
  reservationId?: number;
  ownerVenueId?: number;
  accountTab?: "notifications";
};

export function normalizePagePath(pathname: string): string {
  return pathname === "/" || pathname.endsWith("//") ? pathname : pathname.replace(/\/$/, "");
}

const pagePaths = new Set([
  "/", "/booking", "/account", "/account/security", "/account/notifications",
  "/owner", "/owner/analytics", "/owner/stays", "/owner/rentals", "/owner/sales",
  "/saved", "/stays", "/rentals", "/sales", "/moderation", "/help",
  "/verify-email", "/forgot-password", "/reset-password",
]);

export function isKnownPage(pathname: string): boolean {
  const path = normalizePagePath(pathname);
  return pagePaths.has(path)
    // Listing pages retain their own invalid-ID/unavailable feedback.
    || path.startsWith("/properties/")
    || /^\/owner\/properties\/[^/]+\/preview$/.test(path)
    || /^\/account\/reservations\/\d+$/.test(path)
    || /^\/owner\/venues\/\d+$/.test(path);
}

export function parseApplicationRoute(pathname: string): ApplicationRoute {
  if (/^\/account\/notifications\/?$/.test(pathname))
    return { page: "account", accountTab: "notifications" };
  const reservation = pathname.match(/^\/account\/reservations\/(\d+)\/?$/);
  if (reservation)
    return { page: "account", reservationId: Number(reservation[1]) };
  const venue = pathname.match(/^\/owner\/venues\/(\d+)\/?$/);
  if (venue) return { page: "owner", ownerVenueId: Number(venue[1]) };
  if (pathname === "/account" || pathname.startsWith("/account/"))
    return { page: "account" };
  if (pathname === "/owner" || pathname.startsWith("/owner/"))
    return { page: "owner" };
  return { page: "home" };
}
