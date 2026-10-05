import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { propertySearchPath, readPropertySearch } from "./property-search-url";
import { normalizedSearchPath } from "./saved-searches";
import PropertyMapLocationFields from "./PropertyMapLocationFields";

it("preserves map bounds with other filters in shared and saved searches", () => {
  const path = "/?city=Beograd&offer_type=sale&map_only=true&map_south=44.7&map_north=44.9&map_west=20.3&map_east=20.6&rooms=0&offset=12";
  const state = readPropertySearch(path.slice(1));
  expect(state.filters).toMatchObject({ map_only: true, map_south: 44.7, map_north: 44.9, map_west: 20.3, map_east: 20.6, rooms: 0 });
  expect(readPropertySearch(propertySearchPath(state).slice(1))).toEqual(state);
  expect(normalizedSearchPath(path)).toContain("map_south=44.7");
  expect(normalizedSearchPath(path)).not.toContain("offset");
});

it.each(["map_south=44", "map_south=NaN&map_north=45&map_west=20&map_east=21", "map_south=44&map_north=45&map_west=180&map_east=-180"])("drops invalid or partial bounds: %s", query => {
  expect(readPropertySearch(`?${query}`).filters).toEqual({});
});

it("requires explicit map opt-in and removes coordinates from the form when disabled", async () => {
  const user = userEvent.setup();
  const { container } = render(<form><PropertyMapLocationFields value={null} /></form>);
  const toggle = screen.getByRole("checkbox", { name: "Prikaži približnu lokaciju na javnoj mapi" });
  expect(toggle).not.toBeChecked();
  expect(screen.queryByLabelText("Geografska širina")).not.toBeInTheDocument();
  await user.click(toggle);
  await user.type(screen.getByLabelText("Geografska širina"), "44.81");
  await user.type(screen.getByLabelText("Geografska dužina"), "20.46");
  expect(new FormData(container.querySelector("form")!).get("map_latitude")).toBe("44.81");
  await user.click(toggle);
  expect(new FormData(container.querySelector("form")!).has("map_latitude")).toBe(false);
  expect(screen.queryByLabelText("Interaktivna mapa")).not.toBeInTheDocument();
});
