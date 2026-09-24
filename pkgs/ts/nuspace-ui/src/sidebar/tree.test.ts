import { describe, expect, it } from "vitest";
import { showsNoPlanes, visibleRows } from "./tree";
import { childrenOf, coerceTree, ROOT_ID } from "./types";
import { dropMove } from "./useRailDrag";

// home, a (with a1, a2), b at the top.
const tree = coerceTree([
	{ id: ROOT_ID, kind: "space", title: "", parent: ROOT_ID, children: ["home", "a", "b"] },
	{ id: "home", kind: "plane", title: "Home", parent: ROOT_ID, children: [] },
	{ id: "a", kind: "plane", title: "A", parent: ROOT_ID, children: ["a1", "a2"] },
	{ id: "a1", kind: "plane", title: "A1", parent: "a", children: [] },
	{ id: "a2", kind: "plane", title: "A2", parent: "a", children: [] },
	{ id: "b", kind: "plane", title: "B", parent: ROOT_ID, children: [], made_by: "runs" },
	{ id: "g", kind: "group", title: "Old", parent: ROOT_ID, children: [] },
]);

const rows = visibleRows(tree, childrenOf(tree, ROOT_ID), new Set(["a"]));
const row = (key: string) => rows.find((r) => r.key === key);

describe("sidebar tree", () => {
	it("flattens one tree in sibling order, dropping unknown kinds", () => {
		expect(rows.map((r) => [r.key, r.depth])).toEqual([
			["home", 0],
			["a", 0],
			["a1", 1],
			["a2", 1],
			["b", 0],
		]);
		expect(tree.g).toBeUndefined();
		expect(row("b")?.made_by).toBe("runs");
	});

	it("places a drop before, after, into, and at the end", () => {
		expect(dropMove(tree, "b", { key: "home", edge: "before" }, row("home"))).toEqual({
			parent: ROOT_ID,
			index: 0,
		});
		expect(dropMove(tree, "b", { key: "a1", edge: "after" }, row("a1"))).toEqual({
			parent: "a",
			index: 1,
		});
		expect(dropMove(tree, "b", { key: "a2", edge: "into" }, row("a2"))).toEqual({
			parent: "a2",
			index: 0,
		});
		// After an open row with children showing is its first child.
		expect(dropMove(tree, "b", { key: "a", edge: "after" }, row("a"))).toEqual({
			parent: "a",
			index: 0,
		});
		expect(dropMove(tree, "a1", { key: "", edge: "after" }, undefined)).toEqual({
			parent: ROOT_ID,
			index: 3,
		});
	});

	it("says nothing moves when the row lands where it is", () => {
		expect(dropMove(tree, "a", { key: "home", edge: "after" }, row("home"))).toBeNull();
		expect(dropMove(tree, "b", { key: "", edge: "after" }, undefined)).toBeNull();
	});

	it("unfolds a leaf into the no planes line, and only a leaf", () => {
		const open = visibleRows(tree, childrenOf(tree, ROOT_ID), new Set(["a", "b"]));
		const at = (key: string) => open.find((r) => r.key === key);
		expect(open.map((r) => r.key)).toEqual(["home", "a", "a1", "a2", "b"]);
		const b = at("b");
		const a = at("a");
		expect(b && showsNoPlanes(b)).toBe(true);
		expect(a && showsNoPlanes(a)).toBe(false);
		const home = at("home");
		expect(home && showsNoPlanes(home)).toBe(false);
	});
});
