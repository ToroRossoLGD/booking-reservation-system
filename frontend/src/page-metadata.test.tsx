import { render } from "@testing-library/react";
import { expect, it } from "vitest";
import { routeMetadata, SITE_TITLE, usePageMetadata, type PageMetadata } from "./page-metadata";

function Detail({ metadata }: { metadata: PageMetadata }) {
  usePageMetadata(metadata);
  return null;
}
function Page({ path, detail }: { path: string; detail?: PageMetadata }) {
  usePageMetadata(detail ? null : routeMetadata(path));
  return detail ? <Detail metadata={detail} /> : null;
}
const content = (selector: string) => document.head.querySelector(selector)?.getAttribute("content");

it("replaces public listing metadata on navigation without duplicates or stale titles", () => {
  const { rerender, unmount } = render(<Page path="/stays" />);
  expect(document.title).toBe("Moji boravci | Bookica");
  rerender(<Page path="/properties/7" detail={{ title: "Stan pored reke | Bookica", description: "Prodaja · Novi Sad" }} />);
  expect(document.title).toBe("Stan pored reke | Bookica");
  expect(content('meta[property="og:description"]')).toBe("Prodaja · Novi Sad");
  rerender(<Page path="/properties/7" detail={{ title: "Oglas | Bookica", description: "Učitavanje" }} />);
  expect(content('meta[name="twitter:title"]')).toBe("Oglas | Bookica");
  rerender(<Page path="/owner/stays" />);
  expect(document.title).toBe("Rezervacije tvojih stanova | Bookica");
  expect(document.head.querySelectorAll('meta[name="description"]')).toHaveLength(1);
  expect(content('meta[property="og:title"]')).toBe(document.title);
  rerender(<Page path="/" />);
  expect(document.title).toBe(SITE_TITLE);
  unmount();
  expect(document.head.querySelector('meta[property="og:title"]')).toBeNull();
});

it("restores the static document head on unmount and treats listing titles as text", () => {
  const original = document.title;
  document.title = "Static title";
  const description = document.createElement("meta");
  description.name = "description";
  description.content = "Static description";
  document.head.append(description);
  const title = '<img src=x onerror="alert(1)"> | Bookica';
  const { unmount } = render(<Detail metadata={{ title, description: "Public summary" }} />);
  expect(content('meta[property="og:title"]')).toBe(title);
  expect(document.head.querySelector("img")).toBeNull();
  unmount();
  expect(document.title).toBe("Static title");
  expect(description.content).toBe("Static description");
  description.remove();
  document.title = original;
});

it.each([
  ["/forgot-password", "Zaboravljena lozinka"],
  ["/reset-password", "Nova lozinka"],
  ["/verify-email", "Potvrda email adrese"],
  ["/owner/properties/7/preview", "Pregled tvog oglasa"],
  ["/account/reservations/42", "Detalji rezervacije"],
  ["/owner/analytics/", "Statistika oglasa"],
  ["/sales", "Moji upiti za kupovinu"],
])("names %s without private IDs or account details", (path, title) => {
  expect(routeMetadata(path).title).toBe(`${title} | Bookica`);
  expect(JSON.stringify(routeMetadata(path))).not.toContain("42");
});

it("never copies query/hash tokens into metadata", () => {
  window.history.replaceState(null, "", "/reset-password?token=secret-query#secret-fragment");
  const { unmount } = render(<Page path={window.location.pathname} />);
  expect(document.title).toBe("Nova lozinka | Bookica");
  expect(document.head.innerHTML).not.toContain("secret-query");
  expect(document.head.innerHTML).not.toContain("secret-fragment");
  unmount();
});
