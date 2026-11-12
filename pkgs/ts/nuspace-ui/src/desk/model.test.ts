// The desk model: reading the store (older shapes dropped), item ids, every
// move, the strip rules, navigate / reset / save and the strip dedupe.

import { describe, expect, it } from "vitest";
import {
	addItem,
	addPane,
	closeColumn,
	closeItem,
	closePane,
	type Desk,
	type Item,
	isDeskId,
	isItemId,
	type Link,
	locate,
	MIN_WIDTH,
	makeStrip,
	mintDeskId,
	mintItemId,
	moveItem,
	movePane,
	navigate,
	type Pane,
	type PlaneItem,
	putItem,
	readDesk,
	rename,
	reset,
	type Strip,
	save,
	setShares,
	setWidth,
	shown,
	shownLinks,
	takeItem,
	takePane,
	tidy,
} from "./model";

const L = (plane: string, params: Record<string, string> = {}): Link => ({ plane, params });

function pi(id: string, plane: string, recent?: Link): PlaneItem {
	return recent
		? { id, kind: "plane", original: L(plane), recent }
		: { id, kind: "plane", original: L(plane) };
}

function pn(plane: string, share = 1, recent?: Link): Pane {
	return recent ? { share, original: L(plane), recent } : { share, original: L(plane) };
}

/** A strip of one column per pane list, each at the default width. */
function st(id: string, ...columns: Pane[][]): Strip {
	return { id, kind: "strip", columns: columns.map((panes) => ({ panes })) };
}

function dk(...items: Item[]): Desk {
	return { name: "D", items };
}

/** The desk drawn as text: plane items as their shown plane, strips as columns of shown planes. */
function sketch(desk: Desk): unknown[] {
	return desk.items.map((i) =>
		i.kind === "plane"
			? `${i.id}:${shown(i).plane}`
			: { [i.id]: i.columns.map((c) => c.panes.map((p) => shown(p).plane)) },
	);
}

/** A random source that walks a fixed list, for minting. */
function seq(...values: number[]): () => number {
	let i = 0;
	return () => values[i++ % values.length];
}

const AB = () => dk(pi("aaaaaa", "a"), st("ssssss", [pn("b")], [pn("c")]), pi("dddddd", "d"));

// -- reading ------------------------------------------------------------------

describe("readDesk", () => {
	it("reads the items shape, recent and all", () => {
		const raw = {
			name: "Favorites",
			items: [
				{ id: "k3x9ab", kind: "plane", original: L("p"), recent: L("p", { run: "43" }) },
				{
					id: "q7m2zz",
					kind: "strip",
					columns: [
						{ width: 700, panes: [{ share: 1, original: L("x") }] },
						{ panes: [{ share: 1, original: L("y") }] },
					],
				},
			],
		};
		expect(readDesk(raw)).toEqual(raw);
	});

	it("drops older shapes", () => {
		expect(readDesk({ name: "Old", strips: [] })).toBeNull();
		expect(readDesk({ name: "Old", columns: [] })).toBeNull();
		expect(readDesk({ name: "Old", columns: [], items: [] })).toBeNull();
	});

	it("drops the malformed", () => {
		expect(readDesk(null)).toBeNull();
		expect(readDesk([])).toBeNull();
		expect(readDesk({ name: "x" })).toBeNull();
		expect(readDesk({ name: 3, items: [] })).toBeNull();
		expect(readDesk({ items: [{ id: "bad", kind: "plane", original: L("p") }] })).toBeNull();
		expect(readDesk({ items: [{ id: "aaaaaa", kind: "nope", original: L("p") }] })).toBeNull();
		expect(
			readDesk({ items: [{ id: "aaaaaa", kind: "plane", original: { plane: "" } }] }),
		).toBeNull();
		expect(
			readDesk({ items: [{ id: "aaaaaa", kind: "plane", original: L("p"), recent: 3 }] }),
		).toBeNull();
		expect(
			readDesk({ items: [{ id: "aaaaaa", kind: "strip", columns: [{ width: 1 }] }] }),
		).toBeNull();
		const twice = { items: [pi("aaaaaa", "p"), pi("aaaaaa", "q")] };
		expect(readDesk(twice)).toBeNull();
	});

	it("keeps an empty desk", () => {
		expect(readDesk({ name: "New desk", items: [] })).toEqual({ name: "New desk", items: [] });
	});

	it("drops bad widths (any positive px is good), fixes bad shares, drops a recent equal to its original, and applies the strip rules", () => {
		const raw = {
			name: "D",
			items: [
				{ id: "aaaaaa", kind: "plane", original: L("p"), recent: L("p") },
				{
					id: "ssssss",
					kind: "strip",
					columns: [
						{ width: -3, panes: [{ share: -1, original: L("x") } as Pane, pn("y", 3)] },
						{ width: 640.4, panes: [pn("v")] },
					],
				},
				{ id: "oooooo", kind: "strip", columns: [{ width: 2, panes: [pn("z", 1, L("w"))] }] },
				{ id: "eeeeee", kind: "strip", columns: [] },
			],
		};
		const desk = readDesk(raw) as Desk;
		expect(desk.items[0]).toEqual(pi("aaaaaa", "p"));
		const fixed = desk.items[1] as Strip;
		expect(fixed.columns[0].panes.map((p) => p.share)).toEqual([0.5, 0.5]);
		expect(fixed.columns.map((c) => c.width)).toEqual([undefined, 640.4]);
		expect("width" in fixed.columns[0]).toBe(false);
		expect(desk.items[2]).toEqual(pi("oooooo", "z", L("w")));
		expect(desk.items).toHaveLength(3);
	});
});

describe("ids", () => {
	it("mints desk ids of 8 and item ids of 6, unique", () => {
		expect(isDeskId(mintDeskId(() => false))).toBe(true);
		const desk = dk(pi("aaaaaa", "p"));
		const id = mintItemId(desk, seq(0, 0, 0, 0, 0, 0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5));
		expect(isItemId(id)).toBe(true);
		expect(id).not.toBe("aaaaaa");
		expect(isItemId("abc123")).toBe(true);
		expect(isItemId("ABC123")).toBe(false);
		expect(isItemId("abc12")).toBe(false);
	});
});

describe("reading helpers", () => {
	it("shows recent over original, and says what an item shows", () => {
		expect(shown(pi("aaaaaa", "p", L("q")))).toEqual(L("q"));
		expect(
			shownLinks(st("ssssss", [pn("b", 0.5), pn("c", 0.5, L("e"))], [pn("d")])).map((l) => l.plane),
		).toEqual(["b", "e", "d"]);
		expect(locate(st("ssssss", [pn("b")], [pn("c", 1, L("e"))]), "e")).toEqual({
			column: 1,
			pane: 0,
		});
		expect(locate(st("ssssss", [pn("b")], [pn("c", 1, L("e"))]), "c")).toBeNull();
	});
});

// -- items ----------------------------------------------------------------------

describe("items", () => {
	it("moves an item between items, the index as drawn before the move", () => {
		const desk = AB();
		expect(sketch(moveItem(desk, "aaaaaa", 3))).toEqual([
			{ ssssss: [["b"], ["c"]] },
			"dddddd:d",
			"aaaaaa:a",
		]);
		expect(sketch(moveItem(desk, "dddddd", 0))[0]).toBe("dddddd:d");
		expect(moveItem(desk, "aaaaaa", 0)).toBe(desk);
		expect(moveItem(desk, "aaaaaa", 1)).toBe(desk);
		expect(moveItem(desk, "zzzzzz", 1)).toBe(desk);
	});

	it("takes an item out and puts it in another desk, keeping its links, minting an id on a clash", () => {
		const from = dk(pi("aaaaaa", "a", L("x")));
		const taken = takeItem(from, "aaaaaa");
		expect(taken?.desk.items).toEqual([]);
		const into = dk(pi("aaaaaa", "q"));
		const next = putItem(into, taken?.item as Item, 0, seq(0.9));
		expect(next.items[0]).toMatchObject({ kind: "plane", original: L("a"), recent: L("x") });
		expect(next.items[0].id).not.toBe("aaaaaa");
		expect(putItem(dk(), taken?.item as Item, 0).items[0].id).toBe("aaaaaa");
	});

	it("closes an item, an empty desk staying", () => {
		const one = dk(pi("aaaaaa", "a"));
		expect(closeItem(one, "aaaaaa")).toEqual({ name: "D", items: [] });
		expect(closeItem(one, "zzzzzz")).toBe(one);
	});

	it("renames", () => {
		const desk = AB();
		expect(rename(desk, "D")).toBe(desk);
		expect(rename(desk, "E").name).toBe("E");
	});

	it("never mutates its input", () => {
		const desk = AB();
		const copy = JSON.parse(JSON.stringify(desk));
		moveItem(desk, "aaaaaa", 3);
		closePane(desk, "ssssss", "b");
		navigate(desk, "aaaaaa", L("q"));
		save(desk, "aaaaaa");
		expect(desk).toEqual(copy);
	});
});

// -- strips -----------------------------------------------------------------------

describe("strips", () => {
	it("makes a strip of a plane item and a dropped link, same id, on a side", () => {
		const desk = dk(pi("aaaaaa", "a", L("x")));
		const right = makeStrip(desk, "aaaaaa", { original: L("b") }, "right");
		expect(right.items[0]).toEqual(st("aaaaaa", [pn("a", 1, L("x"))], [pn("b")]));
		expect(sketch(makeStrip(desk, "aaaaaa", { original: L("b") }, "left"))).toEqual([
			{ aaaaaa: [["b"], ["x"]] },
		]);
		expect(makeStrip(desk, "aaaaaa", { original: L("x") }, "right")).toBe(desk);
		const s = dk(st("ssssss", [pn("b")], [pn("c")]));
		expect(makeStrip(s, "ssssss", { original: L("d") }, "right")).toBe(s);
	});

	it("makes a strip of a plane item and a dropped link stacked in one column", () => {
		const desk = dk(pi("aaaaaa", "a", L("x")));
		const below = makeStrip(desk, "aaaaaa", { original: L("b") }, "bottom");
		expect(below.items[0]).toEqual(st("aaaaaa", [pn("a", 0.5, L("x")), pn("b", 0.5)]));
		expect(sketch(makeStrip(desk, "aaaaaa", { original: L("b") }, "top"))).toEqual([
			{ aaaaaa: [["b", "x"]] },
		]);
		expect(makeStrip(desk, "aaaaaa", { original: L("x") }, "top")).toBe(desk);
	});

	it("adds a pane at a strip drop: new column, stacked, at a pane's edge", () => {
		const desk = AB();
		const x = { original: L("x") };
		expect(sketch(addPane(desk, "ssssss", x, { at: 1 }))[1]).toEqual({
			ssssss: [["b"], ["x"], ["c"]],
		});
		expect(sketch(addPane(desk, "ssssss", x, { at: 9 }))[1]).toEqual({
			ssssss: [["b"], ["c"], ["x"]],
		});
		const stacked = addPane(desk, "ssssss", x, { column: 0 });
		expect(sketch(stacked)[1]).toEqual({ ssssss: [["b", "x"], ["c"]] });
		expect((stacked.items[1] as Strip).columns[0].panes.map((p) => p.share)).toEqual([0.5, 0.5]);
		expect(sketch(addPane(desk, "ssssss", x, { plane: "c", edge: "left" }))[1]).toEqual({
			ssssss: [["b"], ["x"], ["c"]],
		});
		expect(sketch(addPane(desk, "ssssss", x, { plane: "c", edge: "top" }))[1]).toEqual({
			ssssss: [["b"], ["x", "c"]],
		});
		expect(sketch(addPane(desk, "ssssss", x, { plane: "c", edge: "bottom" }))[1]).toEqual({
			ssssss: [["b"], ["c", "x"]],
		});
	});

	it("refuses a pane a strip shows already, a missing target, a plane item", () => {
		const desk = AB();
		expect(addPane(desk, "ssssss", { original: L("b") }, { at: 0 })).toBe(desk);
		expect(addPane(desk, "ssssss", { original: L("q"), recent: L("c") }, { at: 0 })).toBe(desk);
		expect(addPane(desk, "ssssss", { original: L("x") }, { plane: "zz", edge: "top" })).toBe(desk);
		expect(addPane(desk, "aaaaaa", { original: L("x") }, { at: 0 })).toBe(desk);
	});

	it("moves a pane in its strip, keeping its width when alone", () => {
		const desk = dk(st("ssssss", [pn("b")], [pn("c")], [pn("d")]));
		(desk.items[0] as Strip).columns[0].width = 400;
		const next = movePane(desk, "ssssss", "b", { at: 3 });
		expect(sketch(next)).toEqual([{ ssssss: [["c"], ["d"], ["b"]] }]);
		expect((next.items[0] as Strip).columns[2].width).toBe(400);
		expect(sketch(movePane(desk, "ssssss", "b", { plane: "d", edge: "top" }))).toEqual([
			{ ssssss: [["c"], ["b", "d"]] },
		]);
		expect(movePane(desk, "ssssss", "b", { plane: "b", edge: "left" })).toBe(desk);
		expect(movePane(desk, "ssssss", "b", { at: 0 })).toBe(desk);
	});

	it("takes a pane out with its links, the strip of one left becoming a plane item in place", () => {
		const desk = dk(pi("aaaaaa", "a"), st("ssssss", [pn("b", 1, L("e"))], [pn("c", 1, L("f"))]));
		const lifted = takePane(desk, "ssssss", "e");
		expect(lifted?.pane).toEqual({ original: L("b"), recent: L("e") });
		expect(lifted?.width).toBeUndefined();
		expect(lifted?.desk.items[1]).toEqual(pi("ssssss", "c", L("f")));
		expect(takePane(desk, "ssssss", "b")).toBeNull();
	});

	it("closes a pane, a column, the strip rules after", () => {
		const desk = dk(st("ssssss", [pn("b", 0.5), pn("x", 0.5)], [pn("c")]));
		expect(sketch(closePane(desk, "ssssss", "x"))).toEqual([{ ssssss: [["b"], ["c"]] }]);
		expect((closePane(desk, "ssssss", "x").items[0] as Strip).columns[0].panes[0].share).toBe(1);
		expect(sketch(closeColumn(desk, "ssssss", 1))).toEqual([{ ssssss: [["b", "x"]] }]);
		expect(sketch(closeColumn(desk, "ssssss", 0))).toEqual(["ssssss:c"]);
		expect(closeColumn(desk, "ssssss", 5)).toBe(desk);
		const two = dk(st("ssssss", [pn("b")], [pn("c")]));
		expect(sketch(closePane(closePane(two, "ssssss", "b"), "ssssss", "c"))).toEqual(["ssssss:c"]);
	});

	it("starts every column of a strip that grows past one at the default width, and keeps widths after", () => {
		const one = dk(pi("aaaaaa", "a"));
		const made = makeStrip(one, "aaaaaa", { original: L("b") }, "right").items[0] as Strip;
		expect(made.columns.map((c) => c.width)).toEqual([undefined, undefined]);
		// A strip of one stacked column, its width anything: a second column drops it.
		const tall = dk(st("ssssss", [pn("b", 0.5), pn("x", 0.5)]));
		(tall.items[0] as Strip).columns[0].width = 900;
		const two = addPane(tall, "ssssss", { original: L("n") }, { at: 1 }).items[0] as Strip;
		expect(two.columns.map((c) => c.width)).toEqual([undefined, undefined]);
		// Past two, the columns there keep what they have.
		const wide = dk(st("ssssss", [pn("b")], [pn("c")]));
		(wide.items[0] as Strip).columns[0].width = 400;
		const three = addPane(wide, "ssssss", { original: L("n") }, { at: 2 }).items[0] as Strip;
		expect(three.columns.map((c) => c.width)).toEqual([400, undefined, undefined]);
	});

	it("resizes columns and sets shares", () => {
		const desk = AB();
		expect((setWidth(desk, "ssssss", "c", 700.4).items[1] as Strip).columns[1].width).toBe(700);
		expect((setWidth(desk, "ssssss", "c", 3).items[1] as Strip).columns[1].width).toBe(MIN_WIDTH);
		expect(setWidth(desk, "ssssss", "c", Number.NaN)).toBe(desk);
		const tall = dk(st("ssssss", [pn("b", 0.5), pn("x", 0.5)], [pn("c")]));
		expect(
			(setShares(tall, "ssssss", "x", [1, 3]).items[0] as Strip).columns[0].panes.map(
				(p) => p.share,
			),
		).toEqual([0.25, 0.75]);
		expect(setShares(tall, "ssssss", "x", [1])).toBe(tall);
	});
});

// -- links ----------------------------------------------------------------------------

describe("navigate, reset, save", () => {
	it("navigate writes the recent of a plane item, landing on the original drops it", () => {
		const desk = dk(pi("aaaaaa", "a"));
		const there = navigate(desk, "aaaaaa", L("a", { run: "43" }));
		expect(there.desk.items[0]).toEqual(pi("aaaaaa", "a", L("a", { run: "43" })));
		expect(there.focus).toBe("a");
		expect(navigate(there.desk, "aaaaaa", L("a")).desk.items[0]).toEqual(pi("aaaaaa", "a"));
		expect(navigate(desk, "aaaaaa", L("a")).desk).toBe(desk);
	});

	it("navigate writes a pane's recent in a strip", () => {
		const desk = AB();
		const there = navigate(desk, "ssssss", L("x"), "b");
		expect((there.desk.items[1] as Strip).columns[0].panes[0]).toEqual(pn("b", 1, L("x")));
		expect(there.focus).toBe("x");
		expect(navigate(desk, "ssssss", L("x"), "nope").desk).toBe(desk);
	});

	it("navigating a pane to a plane another pane shows focuses that pane, nothing changed", () => {
		const desk = AB();
		const there = navigate(desk, "ssssss", L("c", { k: "v" }), "b");
		expect(there.desk).toBe(desk);
		expect(there.focus).toBe("c");
	});

	it("reset drops the recent; in a strip an original shown elsewhere focuses that pane", () => {
		const desk = dk(pi("aaaaaa", "a", L("x")), st("ssssss", [pn("b", 1, L("c2"))], [pn("c")]));
		expect(reset(desk, "aaaaaa").desk.items[0]).toEqual(pi("aaaaaa", "a"));
		expect(reset(desk, "ssssss", "c2").desk.items[1]).toEqual(st("ssssss", [pn("b")], [pn("c")]));
		const clash = dk(st("ssssss", [pn("b", 1, L("x"))], [pn("q", 1, L("b"))]));
		const r = reset(clash, "ssssss", "x");
		expect(r.desk).toBe(clash);
		expect(r.focus).toBe("b");
		expect(reset(desk, "ssssss", "c").desk).toBe(desk);
	});

	it("save makes one item's or pane's recent its original, the rest untouched", () => {
		const desk = dk(
			pi("aaaaaa", "a", L("x", { k: "1" })),
			st("ssssss", [pn("b", 1, L("y"))], [pn("c")]),
		);
		const one = save(desk, "aaaaaa");
		expect(one.items[0]).toEqual({ id: "aaaaaa", kind: "plane", original: L("x", { k: "1" }) });
		expect(one.items[1]).toEqual(desk.items[1]);
		const pane = save(desk, "ssssss", "y");
		expect(pane.items[0]).toEqual(desk.items[0]);
		expect(pane.items[1]).toEqual(st("ssssss", [pn("y")], [pn("c")]));
		expect(save(one, "aaaaaa")).toBe(one);
		expect(save(desk, "ssssss", "c")).toBe(desk);
	});
});

describe("tidy", () => {
	it("keeps a strip from showing a plane twice", () => {
		const desk = dk(st("ssssss", [pn("b")], [pn("c", 1, L("b"))], [pn("d")]));
		expect(sketch(tidy(desk))).toEqual([{ ssssss: [["b"], ["d"]] }]);
	});

	it("adds an item through addItem as a copy", () => {
		const item = pi("nnnnnn", "n", L("m"));
		const next = addItem(dk(), item, 0);
		expect(next.items[0]).toEqual(item);
		expect(next.items[0]).not.toBe(item);
	});
});
