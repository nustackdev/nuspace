// The layout model: reading order, and above all what a drop sends. Given a
// drag source and a drop spot, which `layout.*` event goes out with which
// payload, or none.

import { describe, expect, it } from "vitest";
import { coerceLayout, type LayoutItem } from "../types";
import {
	dropOp,
	inReadingOrder,
	itemsInOrder,
	readingOrder,
	resized,
	type Source,
	type Spot,
	sharesOf,
	spotUnder,
	stepItems,
	withColumn,
	withoutCell,
} from "./model";

const P = "p_one";
const Q = "p_two";

// p_one:  i1 a  |  i2 strip [b, c] [d]  |  i3 e
const L: LayoutItem[] = [
	{ id: "i1", kind: "cell", cell: "a" },
	{
		id: "i2",
		kind: "strip",
		columns: [
			{ cells: ["b", "c"], share: 0.5 },
			{ cells: ["d"], share: 0.5 },
		],
	},
	{ id: "i3", kind: "cell", cell: "e" },
];

// p_two:  q1 x  |  q2 strip [y] [z]
const LQ: LayoutItem[] = [
	{ id: "q1", kind: "cell", cell: "x" },
	{
		id: "q2",
		kind: "strip",
		columns: [
			{ cells: ["y"], share: 0.5 },
			{ cells: ["z"], share: 0.5 },
		],
	},
];

const cell = (c: string, plane = P): Source => ({ kind: "cell", plane, cell: c });
const gap = (index: number, plane = P): Spot => ({ kind: "gap", plane, index });
const side = (c: string, s: "left" | "right", plane = P): Spot => ({
	kind: "side",
	plane,
	cell: c,
	side: s,
});
const column = (i: string, k: number, index: number, plane = P): Spot => ({
	kind: "column",
	plane,
	item: i,
	column: k,
	index,
});
const end = (plane: string): Spot => ({ kind: "end", plane });

/** A drop within p_one, or from p_one onto p_two. */
const drop = (source: Source, spot: Spot) => dropOp(source, spot, L, spot.plane === Q ? LQ : L);

const third = 1 / 3;
const strip = (...columns: [string[], number][]) => ({
	kind: "strip" as const,
	columns: columns.map(([cells, share]) => ({ cells, share })),
});

/** `layout.set` of `id` to `columns`, shares to within float noise. */
function expectSet(got: ReturnType<typeof drop>, id: string, columns: [string[], number][]) {
	expect(got?.op).toBe("layout.set");
	const args = got?.args as { item_id: string; item: ReturnType<typeof strip> };
	expect(args.item_id).toBe(id);
	expect(args.item.kind).toBe("strip");
	expect(args.item.columns.map((c) => c.cells)).toEqual(columns.map(([cells]) => cells));
	args.item.columns.forEach((c, i) => {
		expect(c.share).toBeCloseTo(columns[i][1]);
	});
}

describe("reading order", () => {
	it("is item by item, a strip column by column", () => {
		expect(readingOrder(L)).toEqual(["a", "b", "c", "d", "e"]);
	});

	it("sorts the cells as drawn, a cell no item holds last", () => {
		const cells = ["e", "z", "d", "c", "b", "a"].map((id) => ({ id }));
		expect(inReadingOrder(cells, L).map((c) => c.id)).toEqual(["a", "b", "c", "d", "e", "z"]);
	});
});

describe("the wire layout", () => {
	const cells = ["a", "b", "c"].map((id) => ({ id }));

	it("is one item per cell when none is shipped", () => {
		expect(coerceLayout(undefined, cells)).toEqual([
			{ id: "a", kind: "cell", cell: "a" },
			{ id: "b", kind: "cell", cell: "b" },
			{ id: "c", kind: "cell", cell: "c" },
		]);
	});

	it("keeps to the cells: a strip left with one reads as a cell item, an unheld cell goes last", () => {
		const raw = [
			{
				id: "s1",
				kind: "strip",
				columns: [
					{ cells: ["a", "gone"], share: 0.5 },
					{ cells: ["gone2"], share: 0.5 },
				],
			},
			{ id: "c1", kind: "cell", cell: "a" },
			{ id: "c2", kind: "cell", cell: "b" },
			{ id: "", kind: "cell", cell: "c" },
		];
		expect(coerceLayout(raw, cells)).toEqual([
			{ id: "s1", kind: "cell", cell: "a" },
			{ id: "c2", kind: "cell", cell: "b" },
			{ id: "c", kind: "cell", cell: "c" },
		]);
	});

	it("rescales the shares of the columns left", () => {
		const raw = [
			{
				id: "s1",
				kind: "strip",
				columns: [
					{ cells: ["a"], share: 0.25 },
					{ cells: ["gone"], share: 0.5 },
					{ cells: ["b"], share: 0.25 },
				],
			},
		];
		const got = coerceLayout(raw, cells)[0];
		expect(got.kind === "strip" && got.columns.map((c) => c.share)).toEqual([0.5, 0.5]);
	});
});

describe("strip rules", () => {
	it("takes a cell out: an empty column goes, the rest rescale", () => {
		const out = withoutCell(
			[
				{ cells: ["b", "c"], share: 0.25 },
				{ cells: ["d"], share: 0.75 },
			],
			"d",
		);
		expect(out).toEqual([{ cells: ["b", "c"], share: 1 }]);
	});

	it("gives a new column 1 / n, the rest giving it up in proportion", () => {
		const out = withColumn([{ cells: ["b"], share: 1 }], 0, ["a"]);
		expect(out).toEqual([
			{ cells: ["a"], share: 0.5 },
			{ cells: ["b"], share: 0.5 },
		]);
	});

	it("turns sizes into shares summing to 1", () => {
		const shares = sharesOf([33.3333, 66.6667]);
		expect(shares[0] + shares[1]).toBe(1);
		expect(shares[0]).toBeCloseTo(third);
	});
});

describe("drop: a cell alone, within its plane", () => {
	it("moves its item to a gap, anchored on the item it lands before", () => {
		expect(drop(cell("a"), gap(2))).toEqual({
			op: "layout.move",
			args: { item_id: "i1", before: "i3" },
		});
		expect(drop(cell("e"), gap(0))).toEqual({
			op: "layout.move",
			args: { item_id: "i3", before: "i1" },
		});
	});

	it("moves to the end with no anchor", () => {
		expect(drop(cell("a"), gap(3))).toEqual({ op: "layout.move", args: { item_id: "i1" } });
	});

	it("sends nothing for the gaps either side of itself", () => {
		expect(drop(cell("a"), gap(0))).toBeNull();
		expect(drop(cell("a"), gap(1))).toBeNull();
		expect(drop(cell("e"), gap(2))).toBeNull();
		expect(drop(cell("e"), gap(3))).toBeNull();
	});

	it("beside a cell alone, makes a strip of the two in that item's place", () => {
		expectSet(drop(cell("a"), side("e", "right")), "i3", [
			[["e"], 0.5],
			[["a"], 0.5],
		]);
		expectSet(drop(cell("a"), side("e", "left")), "i3", [
			[["a"], 0.5],
			[["e"], 0.5],
		]);
	});

	it("beside itself, sends nothing", () => {
		expect(drop(cell("a"), side("a", "left"))).toBeNull();
		expect(drop(cell("a"), side("a", "right"))).toBeNull();
	});

	it("beside a cell in a strip, adds a column on that side of its column", () => {
		expectSet(drop(cell("e"), side("d", "left")), "i2", [
			[["b", "c"], third],
			[["e"], third],
			[["d"], third],
		]);
		expectSet(drop(cell("e"), side("b", "left")), "i2", [
			[["e"], third],
			[["b", "c"], third],
			[["d"], third],
		]);
		expectSet(drop(cell("a"), side("d", "right")), "i2", [
			[["b", "c"], third],
			[["d"], third],
			[["a"], third],
		]);
	});

	it("into a strip's column, places it there by the strip's id", () => {
		expect(drop(cell("a"), column("i2", 1, 1))).toEqual({
			op: "layout.place",
			args: { cell_id: "a", into: "i2", column: 1, index: 1 },
		});
		expect(drop(cell("e"), column("i2", 0, 0))).toEqual({
			op: "layout.place",
			args: { cell_id: "e", into: "i2", column: 0, index: 0 },
		});
	});

	it("is never offered the sidebar's end of its own plane", () => {
		expect(drop(cell("a"), end(P))).toBeNull();
	});
});

describe("drop: a cell of a strip, within its plane", () => {
	it("to a gap, places it out of the strip, anchored on any item, the strip too", () => {
		expect(drop(cell("b"), gap(0))).toEqual({
			op: "layout.place",
			args: { cell_id: "b", before: "i1" },
		});
		expect(drop(cell("b"), gap(1))).toEqual({
			op: "layout.place",
			args: { cell_id: "b", before: "i2" },
		});
		expect(drop(cell("b"), gap(2))).toEqual({
			op: "layout.place",
			args: { cell_id: "b", before: "i3" },
		});
		expect(drop(cell("d"), gap(3))).toEqual({ op: "layout.place", args: { cell_id: "d" } });
	});

	it("beside a cell alone, makes a strip with it (the server takes it out of its own)", () => {
		expectSet(drop(cell("b"), side("a", "right")), "i1", [
			[["a"], 0.5],
			[["b"], 0.5],
		]);
	});

	it("beside a cell of its own strip, regroups the strip", () => {
		// c out of b's column, into a new one right of it.
		expectSet(drop(cell("c"), side("b", "right")), "i2", [
			[["b"], third],
			[["c"], third],
			[["d"], third],
		]);
		// d, alone in its column, to the left of b's: its column goes first.
		expectSet(drop(cell("d"), side("b", "left")), "i2", [
			[["d"], 0.5],
			[["b", "c"], 0.5],
		]);
	});

	it("beside its own strip where it already is, sends nothing", () => {
		expect(drop(cell("d"), side("c", "right"))).toBeNull();
		expect(drop(cell("d"), side("b", "right"))).toBeNull();
	});

	it("within its own column, regroups the strip, the index counted as drawn", () => {
		expectSet(drop(cell("c"), column("i2", 0, 0)), "i2", [
			[["c", "b"], 0.5],
			[["d"], 0.5],
		]);
		expectSet(drop(cell("b"), column("i2", 0, 2)), "i2", [
			[["c", "b"], 0.5],
			[["d"], 0.5],
		]);
	});

	it("within its own column, sends nothing for the spots either side of itself", () => {
		expect(drop(cell("b"), column("i2", 0, 0))).toBeNull();
		expect(drop(cell("b"), column("i2", 0, 1))).toBeNull();
		expect(drop(cell("c"), column("i2", 0, 2))).toBeNull();
		expect(drop(cell("d"), column("i2", 1, 0))).toBeNull();
		expect(drop(cell("d"), column("i2", 1, 1))).toBeNull();
	});

	it("to another column of its strip, regroups it: a column it empties goes", () => {
		expectSet(drop(cell("d"), column("i2", 0, 1)), "i2", [[["b", "d", "c"], 1]]);
		expectSet(drop(cell("b"), column("i2", 1, 1)), "i2", [
			[["c"], 0.5],
			[["d", "b"], 0.5],
		]);
	});

	it("into a column that is not there, sends nothing", () => {
		expect(drop(cell("a"), column("i2", 5, 0))).toBeNull();
		expect(drop(cell("a"), column("i3", 0, 0))).toBeNull();
	});
});

describe("drop: a cell onto another plane", () => {
	it("transfers it to a gap there, anchored on that plane's items", () => {
		expect(drop(cell("a"), gap(0, Q))).toEqual({
			op: "layout.transfer",
			args: { cell_id: "a", plane_id: Q, before: "q1" },
		});
		expect(drop(cell("b"), gap(1, Q))).toEqual({
			op: "layout.transfer",
			args: { cell_id: "b", plane_id: Q, before: "q2" },
		});
		expect(drop(cell("b"), gap(2, Q))).toEqual({
			op: "layout.transfer",
			args: { cell_id: "b", plane_id: Q },
		});
	});

	it("transfers it into a strip's column there", () => {
		expect(drop(cell("e"), column("q2", 1, 0, Q))).toEqual({
			op: "layout.transfer",
			args: { cell_id: "e", plane_id: Q, into: "q2", column: 1, index: 0 },
		});
	});

	it("transfers it to the end from the plane's sidebar row", () => {
		expect(dropOp(cell("d"), end(Q), L, [])).toEqual({
			op: "layout.transfer",
			args: { cell_id: "d", plane_id: Q },
		});
	});

	it("is never offered beside a cell there", () => {
		expect(drop(cell("a"), side("x", "left", Q))).toBeNull();
	});

	it("sends nothing for a cell its plane does not hold", () => {
		expect(drop(cell("nope"), gap(0))).toBeNull();
	});
});

describe("keys", () => {
	it("move the items holding the selection one item up or down, as a block", () => {
		expect(stepItems(L, ["b"], -1)).toEqual(["i2", "i1", "i3"]);
		expect(stepItems(L, ["d"], 1)).toEqual(["i1", "i3", "i2"]);
		expect(stepItems(L, ["c", "e"], -1)).toEqual(["i2", "i3", "i1"]);
	});

	it("move nothing at the edge or with nothing selected", () => {
		expect(stepItems(L, ["a"], -1)).toBeNull();
		expect(stepItems(L, ["e"], 1)).toBeNull();
		expect(stepItems(L, [], 1)).toBeNull();
	});

	it("reorder the items by where the first of their cells is sent", () => {
		expect(itemsInOrder(L, ["e", "a", "b", "c", "d"])).toEqual(["i3", "i1", "i2"]);
		expect(itemsInOrder(L, ["a", "d", "e", "b", "c"])).toEqual(["i1", "i2", "i3"]);
	});
});

describe("a cell made under a strip's cell", () => {
	it("goes into the column under it", () => {
		expect(spotUnder(L, "b")).toEqual({ into: "i2", column: 0, index: 1 });
		expect(spotUnder(L, "d")).toEqual({ into: "i2", column: 1, index: 1 });
	});

	it("stays on its own under a cell alone, or under the plane's last cell", () => {
		expect(spotUnder(L, "a")).toBeNull();
		expect(spotUnder(L.slice(0, 2), "d")).toBeNull();
	});
});

describe("resizing a strip", () => {
	const s = L[1] as Extract<LayoutItem, { kind: "strip" }>;

	it("sets the strip at the new shares", () => {
		expect(resized(s, [0.3, 0.7])).toEqual({
			op: "layout.set",
			args: { item_id: "i2", item: strip([["b", "c"], 0.3], [["d"], 0.7]) },
		});
	});

	it("sends nothing for the shares it has, or the wrong count", () => {
		expect(resized(s, [0.50001, 0.49999])).toBeNull();
		expect(resized(s, [1])).toBeNull();
	});
});
