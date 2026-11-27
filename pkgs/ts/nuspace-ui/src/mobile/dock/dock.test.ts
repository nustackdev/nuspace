// The dock's logic: what the + sheet offers for the screen it is over, and
// the history marks its modes ride on.

import { describe, expect, it } from "vitest";
import { markOf, withMark } from "../entry";
import { controlsFor } from "./model";

describe("controlsFor", () => {
	it("offers everything on a plane that can be written and has cells", () => {
		expect(controlsFor({ plane: "home", editable: true, cells: 3 })).toEqual([
			"cell",
			"plane",
			"edit",
		]);
	});

	it("offers no Add cell on a plane that cannot be written, still Edit cells", () => {
		expect(controlsFor({ plane: "home", editable: false, cells: 3 })).toEqual(["plane", "edit"]);
	});

	it("offers no Edit cells with no cells, or before they land", () => {
		expect(controlsFor({ plane: "home", editable: true, cells: 0 })).toEqual(["cell", "plane"]);
		expect(controlsFor({ plane: "home", editable: true, cells: null })).toEqual(["cell", "plane"]);
	});

	it("offers only Add plane with no plane on screen", () => {
		expect(controlsFor(null)).toEqual(["plane"]);
	});
});

describe("history marks", () => {
	it("reads a mark, nothing off state that is not an object", () => {
		expect(markOf({ state: { k: 1 } }, "k")).toBe(1);
		expect(markOf({ state: null }, "k")).toBeUndefined();
		expect(markOf({ state: [1] }, "k")).toBeUndefined();
		expect(markOf({ state: "x" }, "k")).toBeUndefined();
	});

	it("sets and drops a mark, keeping the rest, null when nothing is left", () => {
		expect(withMark(null, "k", 1)).toEqual({ k: 1 });
		expect(withMark({ a: 1 }, "k", "p")).toEqual({ a: 1, k: "p" });
		expect(withMark({ a: 1, k: "p" }, "k", null)).toEqual({ a: 1 });
		expect(withMark({ k: "p" }, "k", null)).toBeNull();
	});
});
