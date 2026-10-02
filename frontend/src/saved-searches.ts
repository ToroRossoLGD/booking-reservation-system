import { propertySearchPath, readPropertySearch } from "./property-search-url";

export const SAVED_SEARCHES_KEY = "bookica_saved_searches_v1";
export const MAX_SAVED_SEARCHES = 10;
export type SavedSearch = { name: string; path: string };
export type AccountSearch = SavedSearch & { id: number; alerts_enabled?: boolean };

export function normalizedSearchPath(path: string): string | null {
  if (path !== "/" && !path.startsWith("/?")) return null;
  if (path.length > 4000 || path.includes("#")) return null;
  const state = readPropertySearch(path.slice(1));
  return propertySearchPath({ ...state, offset: 0 });
}

export function readSavedSearches(): SavedSearch[] {
  const raw = localStorage.getItem(SAVED_SEARCHES_KEY);
  if (!raw) return [];
  let parsed: unknown;
  try { parsed = JSON.parse(raw); } catch { return []; }
  if (!Array.isArray(parsed)) return [];
  const result: SavedSearch[] = [];
  for (const item of parsed.slice(0, 100)) {
    if (!item || typeof item.name !== "string" || typeof item.path !== "string") continue;
    const name = item.name.trim().slice(0, 60);
    const path = normalizedSearchPath(item.path);
    if (!name || path === null || result.some(existing => existing.path === path)) continue;
    result.push({ name, path });
    if (result.length === MAX_SAVED_SEARCHES) break;
  }
  return result;
}

export function writeSavedSearches(items: SavedSearch[]) {
  localStorage.setItem(SAVED_SEARCHES_KEY, JSON.stringify(items));
}
