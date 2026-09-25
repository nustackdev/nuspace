import { describe, expect, it } from "vitest";
import { pinSlot } from "./PinnedRow";
import { applySidebarWrite } from "./state";

describe("the pins on the wire", () => {
	it("land with the tree, as strings, and empty when left out", () => {
		const props: Record<string, unknown> = {};
		applySidebarWrite(props, { op: "set_tree", planes: [], pinned: ["home", 7] });
		expect(props.pinned).toEqual(["home", "7"]);
		applySidebarWrite(props, { op: "set_tree", planes: [] });
		expect(props.pinned).toEqual([]);
	});
});

import { pinDropIndex, placePin } from "./pin";

describe("placing a pin", () => {
	it("takes the plane out, then puts it at the index, the end when out of range", () => {
		expect(placePin([], "a", -1)).toEqual(["a"]);
		expect(placePin(["a", "b"], "c", 0)).toEqual(["c", "a", "b"]);
		expect(placePin(["a", "b", "c"], "a", 1)).toEqual(["b", "a", "c"]);
		expect(placePin(["a", "b", "c"], "a", 9)).toEqual(["b", "c", "a"]);
		expect(placePin(["a", "b", "c"], "c", -1)).toEqual(["a", "b", "c"]);
	});
});

describe("where a drop on the pins lands", () => {
	it("names the gap an icon's half points at", () => {
		expect(pinSlot({ index: 0, edge: "before" })).toBe(0);
		expect(pinSlot({ index: 0, edge: "after" })).toBe(1);
		expect(pinSlot({ index: 2, edge: "after" })).toBe(3);
	});

	it("pins a tree row at the gap", () => {
		expect(pinDropIndex(["a", "b"], "x", 0)).toBe(0);
		expect(pinDropIndex(["a", "b"], "x", 2)).toBe(2);
	});

	it("moves a pin, counting without it, and ignores a drop where it is", () => {
		// a b c: c before a, a after c.
		expect(pinDropIndex(["a", "b", "c"], "c", 0)).toBe(0);
		expect(pinDropIndex(["a", "b", "c"], "a", 3)).toBe(2);
		expect(placePin(["a", "b", "c"], "a", 2)).toEqual(["b", "c", "a"]);
		// Either side of itself is where it is.
		expect(pinDropIndex(["a", "b", "c"], "b", 1)).toBeNull();
		expect(pinDropIndex(["a", "b", "c"], "b", 2)).toBeNull();
	});
});
