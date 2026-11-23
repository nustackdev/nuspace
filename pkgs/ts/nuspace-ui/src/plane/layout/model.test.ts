// The layout model: reading order, and above all the rows a drop, a key, a
// resize or a create sends. Given a drag source and a drop spot, which op
// goes out with which rows, or none.

import { describe, expect, it } from "vitest";
import { coerceLayout, type LayoutRow } from "../types";
import {
	dropOp,
	inReadingOrder,
	placed,
	readingOrder,
	resized,
	rowKey,
	rowsInOrder,
	type Source,
	type Spot,
	sharesOf,
	stepRows,
	withColumn,
	withNewCell,
	withoutCell,
} from "./model";

const P = "p_one";
const Q = "p_two";

const third = 1 / 3;

const one = (cell: string): LayoutRow => ({ kind: "cell", cell });
const strip = (...columns: [string[], number][]): LayoutRow => ({
	kind: "strip",
	columns: columns.map(([cells, share]) => ({ cells, share })),
});

// p_one:  a  |  strip [b, c] [d]  |  e
const L: LayoutRow[] = [one("a"), strip([["b", "c"], 0.5], [["d"], 0.5]), one("e")];

// p_two:  x  |  strip [y] [z]
const LQ: LayoutRow[] = [one("x"), strip([["y"], 0.5], [["z"], 0.5])];

const cell = (c: string, plane = P): Source => ({ kind: "cell", plane, cell: c });
const gap = (index: number, plane = P): Spot => ({ kind: "gap", plane, index });
const side = (c: string, s: "left" | "right", plane = P): Spot => ({
	kind: "side",
	plane,
	cell: c,
	side: s,
});
const column = (row: string, k: number, index: number, plane = P): Spot => ({
	kind: "column",
	plane,
	row,
	column: k,
	index,
});
const end = (plane: string): Spot => ({ kind: "end", plane });

/** A drop within p_one, or from p_one onto p_two. */
const drop = (source: Source, spot: Spot) => dropOp(source, spot, L, spot.plane === Q ? LQ : L);

/** What the eye sees: a cell row as its cell, a strip as its columns' cells. */
const shown = (rows: readonly LayoutRow[] | null | undefined) =>
	rows?.map((r) => (r.kind === "cell" ? r.cell : r.columns.map((c) => c.cells))) ?? null;

/** The shares of the strip at `at`. */
const sharesAt = (rows: readonly LayoutRow[] | null | undefined, at: number) => {
	const r = rows?.[at];
	return r?.kind === "strip" ? r.columns.map((c) => c.share) : null;
};

/** The rows a drop's `layout.set` carries. */
function setRows(got: ReturnType<typeof drop>): LayoutRow[] {
	expect(got?.op).toBe("layout.set");
	return (got?.args as { rows: LayoutRow[] } | undefined)?.rows ?? [];
}

describe("reading order", () => {
	it("is row by row, a strip column by column", () => {
		expect(readingOrder(L)).toEqual(["a", "b", "c", "d", "e"]);
	});

	it("sorts the cells as drawn, a cell no row holds last", () => {
		const cells = ["e", "z", "d", "c", "b", "a"].map((id) => ({ id }));
		expect(inReadingOrder(cells, L).map((c) => c.id)).toEqual(["a", "b", "c", "d", "e", "z"]);
	});

	it("names a row by its first cell", () => {
		expect(L.map(rowKey)).toEqual(["a", "b", "e"]);
	});
});

describe("the wire layout", () => {
	const cells = ["a", "b", "c"].map((id) => ({ id }));

	it("is one row per cell when none is shipped", () => {
		expect(coerceLayout(undefined, cells)).toEqual([one("a"), one("b"), one("c")]);
	});

	it("keeps to the cells: a strip left with one reads as a cell row, an unheld cell goes last", () => {
		const raw = [
			{
				kind: "strip",
				columns: [
					{ cells: ["a", "gone"], share: 0.5 },
					{ cells: ["gone2"], share: 0.5 },
				],
			},
			{ kind: "cell", cell: "a" },
			{ kind: "cell", cell: "b" },
		];
		expect(coerceLayout(raw, cells)).toEqual([one("a"), one("b"), one("c")]);
	});

	it("rescales the shares of the columns left", () => {
		const raw = [
			{
				kind: "strip",
				columns: [
					{ cells: ["a"], share: 0.25 },
					{ cells: ["gone"], share: 0.5 },
					{ cells: ["b"], share: 0.25 },
				],
			},
		];
		expect(sharesAt(coerceLayout(raw, cells), 0)).toEqual([0.5, 0.5]);
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
	it("moves its row to a gap", () => {
		expect(shown(setRows(drop(cell("a"), gap(2))))).toEqual([[["b", "c"], ["d"]], "a", "e"]);
		expect(shown(setRows(drop(cell("e"), gap(0))))).toEqual(["e", "a", [["b", "c"], ["d"]]]);
		expect(shown(setRows(drop(cell("a"), gap(3))))).toEqual([[["b", "c"], ["d"]], "e", "a"]);
	});

	it("sends nothing for the gaps either side of itself", () => {
		expect(drop(cell("a"), gap(0))).toBeNull();
		expect(drop(cell("a"), gap(1))).toBeNull();
		expect(drop(cell("e"), gap(2))).toBeNull();
		expect(drop(cell("e"), gap(3))).toBeNull();
	});

	it("beside a cell alone, makes a strip of the two in that row's place", () => {
		const right = setRows(drop(cell("a"), side("e", "right")));
		expect(shown(right)).toEqual([
			[["b", "c"], ["d"]],
			[["e"], ["a"]],
		]);
		expect(sharesAt(right, 1)).toEqual([0.5, 0.5]);
		expect(shown(setRows(drop(cell("a"), side("e", "left"))))).toEqual([
			[["b", "c"], ["d"]],
			[["a"], ["e"]],
		]);
	});

	it("beside itself, sends nothing", () => {
		expect(drop(cell("a"), side("a", "left"))).toBeNull();
		expect(drop(cell("a"), side("a", "right"))).toBeNull();
	});

	it("beside a cell in a strip, adds a column on that side of its column", () => {
		const left = setRows(drop(cell("e"), side("d", "left")));
		expect(shown(left)).toEqual(["a", [["b", "c"], ["e"], ["d"]]]);
		for (const s of sharesAt(left, 1) ?? []) expect(s).toBeCloseTo(third);
		expect(shown(setRows(drop(cell("e"), side("b", "left"))))).toEqual([
			"a",
			[["e"], ["b", "c"], ["d"]],
		]);
		expect(shown(setRows(drop(cell("a"), side("d", "right"))))).toEqual([
			[["b", "c"], ["d"], ["a"]],
			"e",
		]);
	});

	it("into a strip's column, at the index as drawn", () => {
		expect(shown(setRows(drop(cell("a"), column("b", 1, 1))))).toEqual([
			[
				["b", "c"],
				["d", "a"],
			],
			"e",
		]);
		expect(shown(setRows(drop(cell("e"), column("b", 0, 0))))).toEqual([
			"a",
			[["e", "b", "c"], ["d"]],
		]);
		expect(sharesAt(setRows(drop(cell("e"), column("b", 0, 0))), 1)).toEqual([0.5, 0.5]);
	});

	it("is never offered the sidebar's end of its own plane", () => {
		expect(drop(cell("a"), end(P))).toBeNull();
	});
});

describe("drop: a cell of a strip, within its plane", () => {
	it("to a gap, out of the strip by the strip rules, the strip's gaps too", () => {
		expect(shown(setRows(drop(cell("b"), gap(0))))).toEqual(["b", "a", [["c"], ["d"]], "e"]);
		expect(shown(setRows(drop(cell("b"), gap(1))))).toEqual(["a", "b", [["c"], ["d"]], "e"]);
		expect(shown(setRows(drop(cell("b"), gap(2))))).toEqual(["a", [["c"], ["d"]], "b", "e"]);
		// d's column empties: it goes, b and c's takes the whole width.
		const out = setRows(drop(cell("d"), gap(3)));
		expect(shown(out)).toEqual(["a", [["b", "c"]], "e", "d"]);
		expect(sharesAt(out, 1)).toEqual([1]);
	});

	it("out of a strip of two, leaves the other a cell row", () => {
		const two: LayoutRow[] = [strip([["a"], 0.5], [["b"], 0.5])];
		const got = dropOp(cell("a"), gap(1), two, two);
		expect(got).toEqual({ op: "layout.set", args: { rows: [one("b"), one("a")] } });
	});

	it("beside a cell alone, makes a strip with it, out of its own", () => {
		expect(shown(setRows(drop(cell("b"), side("a", "right"))))).toEqual([
			[["a"], ["b"]],
			[["c"], ["d"]],
			"e",
		]);
	});

	it("beside a cell of its own strip, regroups the strip", () => {
		// c out of b's column, into a new one right of it.
		const out = setRows(drop(cell("c"), side("b", "right")));
		expect(shown(out)).toEqual(["a", [["b"], ["c"], ["d"]], "e"]);
		for (const s of sharesAt(out, 1) ?? []) expect(s).toBeCloseTo(third);
		// d, alone in its column, to the left of b's: its column goes first.
		const left = setRows(drop(cell("d"), side("b", "left")));
		expect(shown(left)).toEqual(["a", [["d"], ["b", "c"]], "e"]);
		expect(sharesAt(left, 1)).toEqual([0.5, 0.5]);
	});

	it("beside its own strip where it already is, sends nothing", () => {
		expect(drop(cell("d"), side("c", "right"))).toBeNull();
		expect(drop(cell("d"), side("b", "right"))).toBeNull();
	});

	it("within its own column, the index counted as drawn", () => {
		expect(shown(setRows(drop(cell("c"), column("b", 0, 0))))).toEqual([
			"a",
			[["c", "b"], ["d"]],
			"e",
		]);
		expect(shown(setRows(drop(cell("b"), column("b", 0, 2))))).toEqual([
			"a",
			[["c", "b"], ["d"]],
			"e",
		]);
	});

	it("within its own column, sends nothing for the spots either side of itself", () => {
		expect(drop(cell("b"), column("b", 0, 0))).toBeNull();
		expect(drop(cell("b"), column("b", 0, 1))).toBeNull();
		expect(drop(cell("c"), column("b", 0, 2))).toBeNull();
		expect(drop(cell("d"), column("b", 1, 0))).toBeNull();
		expect(drop(cell("d"), column("b", 1, 1))).toBeNull();
	});

	it("to another column of its strip: a column it empties goes", () => {
		const out = setRows(drop(cell("d"), column("b", 0, 1)));
		expect(shown(out)).toEqual(["a", [["b", "d", "c"]], "e"]);
		expect(sharesAt(out, 1)).toEqual([1]);
		expect(shown(setRows(drop(cell("b"), column("b", 1, 1))))).toEqual([
			"a",
			[["c"], ["d", "b"]],
			"e",
		]);
	});

	it("into a column that is not there, sends nothing", () => {
		expect(drop(cell("a"), column("b", 5, 0))).toBeNull();
		expect(drop(cell("a"), column("e", 0, 0))).toBeNull();
		expect(drop(cell("a"), column("nope", 0, 0))).toBeNull();
	});
});

describe("drop: a cell onto another plane", () => {
	/** The rows a drop's `layout.transfer` carries, checked to name the cell and plane. */
	function transferRows(got: ReturnType<typeof drop>, cellId: string): LayoutRow[] {
		expect(got?.op).toBe("layout.transfer");
		const args = got?.args as { cell_id: string; plane_id: string; rows: LayoutRow[] };
		expect([args.cell_id, args.plane_id]).toEqual([cellId, Q]);
		return args.rows;
	}

	it("transfers it to a gap there, with the target's rows", () => {
		expect(shown(transferRows(drop(cell("a"), gap(0, Q)), "a"))).toEqual([
			"a",
			"x",
			[["y"], ["z"]],
		]);
		expect(shown(transferRows(drop(cell("b"), gap(2, Q)), "b"))).toEqual([
			"x",
			[["y"], ["z"]],
			"b",
		]);
	});

	it("transfers it beside a cell alone there, making a strip", () => {
		const rows = transferRows(drop(cell("a"), side("x", "left", Q)), "a");
		expect(shown(rows)).toEqual([
			[["a"], ["x"]],
			[["y"], ["z"]],
		]);
		expect(sharesAt(rows, 0)).toEqual([0.5, 0.5]);
	});

	it("transfers it beside a cell of a strip there, as a new column", () => {
		const rows = transferRows(drop(cell("e"), side("y", "right", Q)), "e");
		expect(shown(rows)).toEqual(["x", [["y"], ["e"], ["z"]]]);
		for (const s of sharesAt(rows, 1) ?? []) expect(s).toBeCloseTo(third);
	});

	it("transfers it into a strip's column there", () => {
		expect(shown(transferRows(drop(cell("e"), column("y", 1, 0, Q)), "e"))).toEqual([
			"x",
			[["y"], ["e", "z"]],
		]);
	});

	it("leaves its own plane's rows alone: that plane heals when it ships again", () => {
		const before = JSON.stringify(L);
		drop(cell("b"), side("x", "right", Q));
		expect(JSON.stringify(L)).toBe(before);
	});

	it("onto the plane's sidebar row, is a plain transfer to its end", () => {
		expect(dropOp(cell("d"), end(Q), L, [])).toEqual({
			op: "cell.transfer",
			args: { cell_id: "d", plane_id: Q },
		});
	});

	it("sends nothing for a cell its plane does not hold", () => {
		expect(drop(cell("nope"), gap(0))).toBeNull();
	});
});

describe("placing", () => {
	it("leaves the rows given as they were", () => {
		const before = JSON.stringify(L);
		placed(L, "c", side("a", "left"));
		placed(L, "d", column("b", 0, 0));
		placed(L, "a", gap(3));
		expect(JSON.stringify(L)).toBe(before);
	});

	it("is null for a gap past the end", () => {
		expect(placed(L, "a", gap(9))).toBeNull();
	});
});

describe("a new cell's rows", () => {
	it("goes on its own row after a cell alone, or at the top", () => {
		expect(shown(withNewCell(L, "n", "a"))).toEqual(["a", "n", [["b", "c"], ["d"]], "e"]);
		expect(shown(withNewCell(L, "n", null))).toEqual(["n", "a", [["b", "c"], ["d"]], "e"]);
	});

	it("goes into the column under a cell of a strip, at any depth", () => {
		expect(shown(withNewCell(L, "n", "b"))).toEqual(["a", [["b", "n", "c"], ["d"]], "e"]);
		expect(shown(withNewCell(L, "n", "c"))).toEqual(["a", [["b", "c", "n"], ["d"]], "e"]);
		expect(shown(withNewCell(L, "n", "d"))).toEqual([
			"a",
			[
				["b", "c"],
				["d", "n"],
			],
			"e",
		]);
		expect(sharesAt(withNewCell(L, "n", "d"), 1)).toEqual([0.5, 0.5]);
	});

	it("goes on its own row at the end after the plane's last cell, even in a strip", () => {
		const tail = L.slice(0, 2);
		expect(shown(withNewCell(tail, "n", "d"))).toEqual(["a", [["b", "c"], ["d"]], "n"]);
		expect(shown(withNewCell(L, "n", "e"))).toEqual(["a", [["b", "c"], ["d"]], "e", "n"]);
	});

	it("goes at the end after a cell no row holds", () => {
		expect(shown(withNewCell(L, "n", "gone"))).toEqual(["a", [["b", "c"], ["d"]], "e", "n"]);
		expect(shown(withNewCell([], "n", "gone"))).toEqual(["n"]);
		expect(shown(withNewCell([], "n", null))).toEqual(["n"]);
	});
});

describe("keys", () => {
	it("move the rows holding the selection one row up or down, as a block", () => {
		expect(shown(stepRows(L, ["b"], -1))).toEqual([[["b", "c"], ["d"]], "a", "e"]);
		expect(shown(stepRows(L, ["d"], 1))).toEqual(["a", "e", [["b", "c"], ["d"]]]);
		expect(shown(stepRows(L, ["c", "e"], -1))).toEqual([[["b", "c"], ["d"]], "e", "a"]);
	});

	it("move nothing at the edge or with nothing selected", () => {
		expect(stepRows(L, ["a"], -1)).toBeNull();
		expect(stepRows(L, ["e"], 1)).toBeNull();
		expect(stepRows(L, [], 1)).toBeNull();
	});

	it("reorder the rows by where the first of their cells is sent", () => {
		expect(shown(rowsInOrder(L, ["e", "a", "b", "c", "d"]))).toEqual([
			"e",
			"a",
			[["b", "c"], ["d"]],
		]);
		expect(rowsInOrder(L, ["a", "d", "e", "b", "c"])).toBeNull();
	});
});

describe("resizing a strip", () => {
	it("sets the strip at the new shares, the other rows as they are", () => {
		const rows = resized(L, "b", [0.3, 0.7]);
		expect(rows).toEqual([one("a"), strip([["b", "c"], 0.3], [["d"], 0.7]), one("e")]);
	});

	it("sends nothing for the shares it has, the wrong count, or no strip", () => {
		expect(resized(L, "b", [0.50001, 0.49999])).toBeNull();
		expect(resized(L, "b", [1])).toBeNull();
		expect(resized(L, "a", [0.5, 0.5])).toBeNull();
	});
});
