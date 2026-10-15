import { useEffect } from "react";
import { isKnownPage, normalizePagePath } from "./routing";

export const SITE_TITLE = "Bookica — Nekretnine za život i odmor";
export const SITE_DESCRIPTION = "Pronađi stan za prodaju, dugoročni najam ili odmor. Bookica — mesto za odmor, prostor za život.";
export type PageMetadata = { title: string; description: string };

const pages: Record<string, [string, string]> = {
  "/help": ["Kako funkcioniše Bookica", "Vodič za boravke, plaćanje na licu mesta, upite za najam i kupovinu i objavljivanje oglasa."],
  "/saved": ["Sačuvani oglasi", "Pregledaj nekretnine koje si sačuvao za kasnije."],
  "/stays": ["Moji boravci", "Pregledaj i upravljaj svojim rezervacijama smeštaja."],
  "/rentals": ["Moji upiti za najam", "Prati upite za dugoročni najam i razgovore sa vlasnicima."],
  "/sales": ["Moji upiti za kupovinu", "Prati upite za kupovinu nekretnina i dogovorene obilaske."],
  "/owner/stays": ["Rezervacije tvojih stanova", "Upravljaj rezervacijama, dostupnošću i boravcima gostiju."],
  "/owner/rentals": ["Upiti za tvoje stanove", "Pregledaj upite za najam i razgovore sa zainteresovanim zakupcima."],
  "/owner/sales": ["Upiti za kupovinu tvojih nekretnina", "Pregledaj upite kupaca i dogovori obilaske nekretnina."],
  "/owner/analytics": ["Statistika oglasa", "Prati preglede i interesovanje za svoje oglase."],
  "/account/security": ["Bezbednost naloga", "Upravljaj pristupom i aktivnim sesijama svog naloga."],
  "/account/notifications": ["Obaveštenja", "Pregledaj obaveštenja o svojim rezervacijama i upitima."],
  "/forgot-password": ["Zaboravljena lozinka", "Zatraži link za promenu lozinke svog Bookica naloga."],
  "/reset-password": ["Nova lozinka", "Postavi novu lozinku za svoj Bookica nalog."],
  "/verify-email": ["Potvrda email adrese", "Potvrdi email adresu svog Bookica naloga."],
  "/moderation": ["Moderacija oglasa", "Pregled prijava i upravljanje objavljivanjem oglasa."],
  "/booking": ["Rezervacije prostora", "Postojeći sistem rezervacija prostora po satu."],
};

export function routeMetadata(pathname: string): PageMetadata {
  const path = normalizePagePath(pathname);
  if (!isKnownPage(path)) return { title: "Stranica nije pronađena | Bookica", description: "Otvori ponudu nekretnina ili svoj Bookica nalog." };
  let page = pages[path];
  if (!page && /^\/owner\/properties\/[^/]+\/preview$/.test(path)) page = ["Pregled tvog oglasa", "Proveri izgled oglasa pre objavljivanja."];
  if (!page && /^\/account\/reservations\/\d+$/.test(path)) page = ["Detalji rezervacije", "Pregledaj i upravljaj svojom rezervacijom prostora."];
  if (!page && /^\/owner(?:\/|$)/.test(path)) page = ["Vlasnički panel", "Upravljaj svojim nekretninama, oglasima i rezervacijama."];
  if (!page && /^\/account(?:\/|$)/.test(path)) page = ["Moj nalog", "Pregledaj rezervacije i podešavanja svog Bookica naloga."];
  return page ? { title: `${page[0]} | Bookica`, description: page[1] } : { title: SITE_TITLE, description: SITE_DESCRIPTION };
}

/** Only pathname/public listing facts enter metadata, never URL tokens or account data. */
export function usePageMetadata(metadata: PageMetadata | null) {
  const title = metadata?.title;
  const description = metadata?.description;
  useEffect(() => {
    if (title === undefined || description === undefined) return;
    const previousTitle = document.title;
    document.title = title;
    const cleanups = ([
      ["name", "description", description],
      ["property", "og:title", title],
      ["property", "og:description", description],
      ["name", "twitter:title", title],
      ["name", "twitter:description", description],
    ] as const).map(([attribute, key, content]) => {
      const existing = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
      const element = existing ?? document.createElement("meta");
      const previous = element.getAttribute("content");
      element.setAttribute(attribute, key);
      element.content = content;
      if (!existing) document.head.append(element);
      return () => {
        if (!existing) element.remove();
        else if (previous === null) element.removeAttribute("content");
        else element.content = previous;
      };
    });
    return () => { document.title = previousTitle; cleanups.forEach(cleanup => cleanup()); };
  }, [title, description]);
}
