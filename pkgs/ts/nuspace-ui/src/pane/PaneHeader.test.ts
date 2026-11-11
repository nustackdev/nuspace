import { describe, expect, it } from "vitest";
import { coerceTree, ROOT_ID, trailOf } from "../sidebar/types";
import { crumbsOf } from "./PaneHeader";

// a > b > c > d, and e at the top.
const tree = coerceTree([
	{ id: ROOT_ID, kind: "space", title: "Space", parent: ROOT_ID, children: ["a", "e"] },
	{ id: "a", kind: "plane", title: "A", parent: ROOT_ID, children: ["b"] },
	{ id: "b", kind: "plane", title: "B", parent: "a", children: ["c"] },
	{ id: "c", kind: "plane", title: "C", parent: "b", children: ["d"] },
	{ id: "d", kind: "plane", title: "D", parent: "c", children: [] },
	{ id: "e", kind: "plane", title: "E", parent: ROOT_ID, children: [] },
]);

const ids = (id: string) => crumbsOf(trailOf(tree, id)).map((c) => (c === "fold" ? "..." : c.id));

describe("pane trail", () => {
	it("is empty for a plane at the top and for one the tree does not hold", () => {
		expect(trailOf(tree, "e")).toEqual([]);
		expect(trailOf(tree, "gone")).toEqual([]);
	});

	it("leaves the space out and runs top first", () => {
		expect(trailOf(tree, "c")).toEqual([
			{ id: "a", title: "A" },
			{ id: "b", title: "B" },
		]);
	});

	it("shows up to two parents, then folds the middle", () => {
		expect(ids("b")).toEqual(["a"]);
		expect(ids("c")).toEqual(["a", "b"]);
		expect(ids("d")).toEqual(["a", "...", "c"]);
	});
});
