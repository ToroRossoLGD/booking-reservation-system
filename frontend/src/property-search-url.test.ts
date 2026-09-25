import { expect, it } from "vitest";
import { propertySearchPath, readPropertySearch } from "./property-search-url";

it("round trips all supported filters including studios, zero price and stay dates", () => {
  const query = "?city=Novi+Sad&offer_type=short_stay&currency=EUR&min_price_cents=0&max_price_cents=7000&min_area_sqm=20&max_area_sqm=50&rooms=0&sort=price_asc&check_in=2030-10-04&check_out=2030-10-07&guests=2&offset=24";
  const state = readPropertySearch(query);
  expect(state).toMatchObject({ city: "Novi Sad", offer: "short_stay", offset: 24, filters: { rooms: 0, min_price_cents: 0, guests: 2 } });
  expect(propertySearchPath(state)).toBe(`/${query}`);
  expect(readPropertySearch(propertySearchPath(state).slice(1))).toEqual(state);
});

it("ignores invalid ranges, enums, partial availability and unknown parameters", () => {
  const state = readPropertySearch("?offer_type=invalid&currency=BAD&rooms=-1&min_area_sqm=50&max_area_sqm=20&sort=price_asc&min_price_cents=5&check_in=2030-10-04&offset=Infinity&token=private");
  expect(state).toEqual({ city: "", offer: "", offset: 0, filters: {} });
  expect(propertySearchPath(state)).toBe("/");
});

it("keeps valid filters while removing unsafe price comparisons and non-stay dates", () => {
  expect(readPropertySearch("?offer_type=short_stay&check_in=0000-01-01&check_out=0000-01-02&guests=1").filters).toEqual({});
  expect(readPropertySearch("?offer_type=sale&min_price_cents=5&sort=price_desc&rooms=0&check_in=2030-10-04&check_out=2030-10-07&guests=2").filters).toEqual({ rooms: 0 });
  expect(readPropertySearch("?offer_type=sale&currency=EUR&min_price_cents=9999999999999&rooms=101&max_area_sqm=1.2").filters).toEqual({ currency: "EUR" });
});

it("normalizes pagination and Unicode city names without creating external URLs", () => {
  expect(readPropertySearch("?offset=25").offset).toBe(24);
  expect(readPropertySearch("?offset=999999999999999999999").offset).toBe(0);
  const city = "Čačak & Novi Sad";
  expect(readPropertySearch(propertySearchPath({ city, offer: "", filters: {}, offset: 0 }).slice(1)).city).toBe(city);
  expect(readPropertySearch(`?city=${"x".repeat(110)}`).city).toHaveLength(100);
});
