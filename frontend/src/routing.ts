export type ApplicationRoute = {
  page: "home" | "account" | "owner";
  reservationId?: number;
  ownerVenueId?: number;
};

export function parseApplicationRoute(pathname: string): ApplicationRoute {
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
