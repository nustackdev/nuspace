import { describe, expect, it } from "vitest";
import { bandAt, dropMove, edgeHolds, moveHint, seamTarget } from "./drag";
import { showsNoPlanes, visibleRows } from "./tree";
import { childrenOf, coerceTree, ROOT_ID } from "./types";

// home, a (with a1, a2), b at the top.
const tree = coerceTree([
	{ id: ROOT_ID, kind: "space", title: "", parent: ROOT_ID, children: ["home", "a", "b"] },
	{ id: "home", kind: "plane", title: "Home", parent: ROOT_ID, children: [] },
	{ id: "a", kind: "plane", title: "A", parent: ROOT_ID, children: ["a1", "a2"] },
	{ id: "a1", kind: "plane", title: "A1", parent: "a", children: [] },
	{ id: "a2", kind: "plane", title: "A2", parent: "a", children: [] },
	{ id: "b", kind: "plane", title: "B", parent: ROOT_ID, children: [], spec: "runs", icon: "" },
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
		expect(row("b")?.spec).toBe("runs");
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

describe("tree drop gaps", () => {
	// home, a, a1, a2, b: gap 4 is between a2 (depth 1) and b (depth 0).
	it("cuts a row 20 / 60 / 20", () => {
		expect(bandAt(5, 28)).toBe("before");
		expect(bandAt(6, 28)).toBe("into");
		expect(bandAt(22, 28)).toBe("into");
		expect(bandAt(23, 28)).toBe("after");
	});

	it("takes an edge once rested, or while the slot open is the gap it names", () => {
		expect(edgeHolds("before", 3, false, null)).toBe("into");
		expect(edgeHolds("before", 3, true, null)).toBe("before");
		// Down from row 2's bottom edge into row 3's top: the same gap 3.
		expect(edgeHolds("before", 3, false, 3)).toBe("before");
		expect(edgeHolds("after", 3, false, 3)).toBe("into");
		expect(edgeHolds("into", 3, true, 3)).toBe("into");
	});

	it("between depths, takes the depth asked for as far as the gap allows", () => {
		// Deep: after a2, in a.
		const deep = seamTarget(rows, 4, 1);
		expect(deep).toEqual({ target: { key: "a2", edge: "after", sibling: true }, depth: 1 });
		expect(dropMove(tree, "home", deep.target, row("a2"))).toEqual({ parent: "a", index: 2 });
		// Out: before b, at the top.
		const out = seamTarget(rows, 4, 0);
		expect(out).toEqual({ target: { key: "b", edge: "before" }, depth: 0 });
		expect(dropMove(tree, "home", out.target, row("b"))).toEqual({ parent: ROOT_ID, index: 1 });
		// Asked deeper or shallower than the gap allows: clamped.
		expect(seamTarget(rows, 4, 5).depth).toBe(1);
		expect(seamTarget(rows, 4, -3).depth).toBe(0);
	});

	it("under the last row, climbs out of it to the depth asked for", () => {
		const nested = visibleRows(tree, childrenOf(tree, ROOT_ID), new Set(["a"])).slice(0, 4);
		// Under a2 with nothing below: depth 0 is after a, not after a2.
		const top = seamTarget(nested, 4, 0);
		expect(top.target).toEqual({ key: "a", edge: "after", sibling: true });
		expect(dropMove(tree, "home", top.target, row("a"))).toEqual({ parent: ROOT_ID, index: 1 });
	});

	it("under an open row with children showing, only its first child", () => {
		expect(seamTarget(rows, 2, 0)).toEqual({ target: { key: "a", edge: "after" }, depth: 1 });
	});

	it("says where a move goes: back here, inside a plane, or the top", () => {
		expect(moveHint(tree, rows, "a1", "a").label).toBe("Move here");
		expect(moveHint(tree, rows, "b", "a")).toEqual({ label: "Move inside", icon: "inside" });
		expect(moveHint(tree, rows, "a1", ROOT_ID).label).toBe("Move to top level");
	});
});
