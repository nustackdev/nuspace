// The shared drag payloads and the drag table: every row of iteration-3's
// table through `planDrop` (pure) and `dropOn` (written through the router),
// a dragged item or pane keeping its original and recent.

import { beforeEach, describe, expect, it } from "vitest";
import {
	currentRoute,
	focusedRoute,
	knownDesks,
	onDeskWrite,
	resetRouter,
	setDesks,
	setRoles,
} from "../core/router";
import {
	canDrop,
	canDropOnSolo,
	dragging,
	dragKind,
	dropOn,
	dropOnSolo,
	endDrag,
	ITEM_MIME,
	PANE_MIME,
	PLANE_MIME,
	planDrop,
	readDrag,
	type Target,
	writeItem,
	writePane,
	writePlane,
} from "./dnd";
import type { Desk, Drop, Item, Link, Pane, PlaneItem, Strip } from "./model";
import { shown } from "./model";

const DESK = "desk0001";
const OTHER = "desk0002";

/** A stand in for the browser's DataTransfer: types and data. */
function transfer(): DataTransfer {
	const data = new Map<string, string>();
	return {
		effectAllowed: "none",
		get types() {
			return [...data.keys()];
		},
		setData: (type: string, value: string) => data.set(type, value),
		getData: (type: string) => data.get(type) ?? "",
	} as unknown as DataTransfer;
}

const L = (plane: string, params: Record<string, string> = {}): Link => ({ plane, params });

function pi(id: string, plane: string, recent?: Link): PlaneItem {
	return recent
		? { id, kind: "plane", original: L(plane), recent }
		: { id, kind: "plane", original: L(plane) };
}

function pn(plane: string, recent?: Link): Pane {
	return recent ? { share: 1, original: L(plane), recent } : { share: 1, original: L(plane) };
}

function st(id: string, ...panes: Pane[]): Strip {
	return { id, kind: "strip", columns: panes.map((p) => ({ panes: [p] })) };
}

function dk(...items: Item[]): Desk {
	return { name: "D", items };
}

function sketch(desk: Desk | undefined): unknown[] {
	return (desk?.items ?? []).map((i) =>
		i.kind === "plane"
			? `${i.id}:${shown(i).plane}`
			: { [i.id]: i.columns.map((c) => c.panes.map((p) => shown(p).plane)) },
	);
}

/** Desk: plane items `a` (navigated to `x`) and `d`, a strip of `b` and `c`. Other: plane item `o`, a strip of `p` and `q`. */
function world(): Record<string, Desk> {
	return {
		[DESK]: dk(
			pi("aaaaaa", "a", L("x")),
			st("ssssss", pn("b"), pn("c", L("e"))),
			pi("dddddd", "d"),
		),
		[OTHER]: dk(pi("oooooo", "o"), st("tttttt", pn("p"), pn("q"))),
	};
}

/** A random source that steps, so minting is the same every run. */
function steps(): () => number {
	let n = 0;
	return () => {
		n = (n + 0.37) % 1;
		return n;
	};
}

const plan = (payload: Parameters<typeof planDrop>[1], target: Parameters<typeof planDrop>[2]) =>
	planDrop(world(), payload, target, steps());

describe("payloads", () => {
	beforeEach(() => endDrag());

	it("carries a bare link, readable mid drag by kind and on drop whole", () => {
		const dt = transfer();
		writePlane(dt, L("p1", { k: "v" }));
		expect(dragKind(dt)).toBe("plane");
		expect(readDrag(dt)).toEqual({ kind: "plane", link: L("p1", { k: "v" }) });
		expect(dragging()).toEqual({ kind: "plane", link: L("p1", { k: "v" }) });
		endDrag();
		expect(dragging()).toBeNull();
	});

	it("reads a plane id written bare", () => {
		const dt = transfer();
		dt.setData(PLANE_MIME, "p1");
		expect(readDrag(dt)).toEqual({ kind: "plane", link: L("p1") });
		writePlane(dt, "p2");
		expect(readDrag(dt)).toEqual({ kind: "plane", link: L("p2") });
	});

	it("carries an item and a pane", () => {
		const a = transfer();
		writeItem(a, DESK, "aaaaaa");
		expect(dragKind(a)).toBe("item");
		expect(readDrag(a)).toEqual({ kind: "item", desk: DESK, item: "aaaaaa" });
		const b = transfer();
		writePane(b, DESK, "ssssss", "b");
		expect(dragKind(b)).toBe("pane");
		expect(readDrag(b)).toEqual({ kind: "pane", desk: DESK, item: "ssssss", plane: "b" });
	});

	it("refuses anything else or a bad payload", () => {
		expect(dragKind(null)).toBeNull();
		expect(readDrag(null)).toBeNull();
		const dt = transfer();
		dt.setData("text/plain", "x");
		expect(dragKind(dt)).toBeNull();
		expect(readDrag(dt)).toBeNull();
		const bad = transfer();
		bad.setData(PANE_MIME, "{nope");
		expect(readDrag(bad)).toBeNull();
		const half = transfer();
		half.setData(ITEM_MIME, JSON.stringify({ desk: DESK }));
		expect(readDrag(half)).toBeNull();
	});
});

describe("the drag table", () => {
	it("tree row onto a desk title: a new plane item at the end", () => {
		const out = plan({ kind: "plane", link: L("n") }, { kind: "end", desk: DESK });
		expect(out?.[DESK].items[3]).toMatchObject({ kind: "plane", original: L("n") });
		expect(out?.[DESK].items).toHaveLength(4);
		expect(Object.keys(out ?? {})).toEqual([DESK]);
	});

	it("tree row between items: a new plane item there", () => {
		const out = plan({ kind: "plane", link: L("n") }, { kind: "between", desk: DESK, index: 1 });
		expect(out?.[DESK].items[1]).toMatchObject({ kind: "plane", original: L("n") });
	});

	it("tree row onto a plane item: a strip in its place, same id", () => {
		const out = plan(
			{ kind: "plane", link: L("n") },
			{ kind: "onto", desk: DESK, item: "dddddd", edge: "right" },
		);
		expect(sketch(out?.[DESK])[2]).toEqual({ dddddd: [["d"], ["n"]] });
	});

	it("tree row inside a strip: a pane there, new column or stacked", () => {
		const between = plan(
			{ kind: "plane", link: L("n") },
			{ kind: "strip", desk: DESK, item: "ssssss", drop: { at: 1 } },
		);
		expect(sketch(between?.[DESK])[1]).toEqual({ ssssss: [["b"], ["n"], ["e"]] });
		const stacked = plan(
			{ kind: "plane", link: L("n") },
			{ kind: "strip", desk: DESK, item: "ssssss", drop: { plane: "e", edge: "bottom" } },
		);
		expect(sketch(stacked?.[DESK])[1]).toEqual({ ssssss: [["b"], ["e", "n"]] });
		const column = plan(
			{ kind: "plane", link: L("n") },
			{ kind: "strip", desk: DESK, item: "ssssss", drop: { column: 0 } },
		);
		expect(sketch(column?.[DESK])[1]).toEqual({ ssssss: [["b", "n"], ["e"]] });
	});

	it("a plane the strip shows already: nothing", () => {
		expect(
			plan(
				{ kind: "plane", link: L("b") },
				{ kind: "strip", desk: DESK, item: "ssssss", drop: { at: 0 } },
			),
		).toBeNull();
	});

	it("plane item row onto a plane item: a strip, the dragged one gone, its recent kept", () => {
		const out = plan(
			{ kind: "item", desk: DESK, item: "aaaaaa" },
			{ kind: "onto", desk: DESK, item: "dddddd", edge: "left" },
		);
		expect(sketch(out?.[DESK])).toEqual([{ ssssss: [["b"], ["e"]] }, { dddddd: [["x"], ["d"]] }]);
		expect((out?.[DESK].items[1] as Strip | undefined)?.columns[0].panes[0]).toMatchObject({
			original: L("a"),
			recent: L("x"),
		});
	});

	it("plane item row inside a strip: a pane there", () => {
		const out = plan(
			{ kind: "item", desk: DESK, item: "dddddd" },
			{ kind: "strip", desk: DESK, item: "ssssss", drop: { at: 2 } },
		);
		expect(sketch(out?.[DESK])).toEqual(["aaaaaa:x", { ssssss: [["b"], ["e"], ["d"]] }]);
	});

	it("an item between items, same desk: moved there", () => {
		const out = plan(
			{ kind: "item", desk: DESK, item: "aaaaaa" },
			{ kind: "between", desk: DESK, index: 3 },
		);
		expect(sketch(out?.[DESK])).toEqual([{ ssssss: [["b"], ["e"]] }, "dddddd:d", "aaaaaa:x"]);
		expect(
			plan({ kind: "item", desk: DESK, item: "aaaaaa" }, { kind: "between", desk: DESK, index: 1 }),
		).toBeNull();
	});

	it("an item between items, another desk: moved there with its links, both desks written", () => {
		const out = plan(
			{ kind: "item", desk: DESK, item: "ssssss" },
			{ kind: "between", desk: OTHER, index: 1 },
		);
		expect(sketch(out?.[OTHER])).toEqual([
			"oooooo:o",
			{ ssssss: [["b"], ["e"]] },
			{ tttttt: [["p"], ["q"]] },
		]);
		expect(sketch(out?.[DESK])).toEqual(["aaaaaa:x", "dddddd:d"]);
		const end = plan({ kind: "item", desk: DESK, item: "aaaaaa" }, { kind: "end", desk: OTHER });
		expect(end?.[OTHER].items[2]).toEqual(pi("aaaaaa", "a", L("x")));
	});

	it("a strip lands only between items", () => {
		expect(
			plan(
				{ kind: "item", desk: DESK, item: "ssssss" },
				{ kind: "onto", desk: DESK, item: "dddddd", edge: "left" },
			),
		).toBeNull();
		expect(
			plan(
				{ kind: "item", desk: OTHER, item: "tttttt" },
				{ kind: "strip", desk: DESK, item: "ssssss", drop: { at: 0 } },
			),
		).toBeNull();
	});

	it("an item onto itself: nothing", () => {
		expect(
			plan(
				{ kind: "item", desk: DESK, item: "dddddd" },
				{ kind: "onto", desk: DESK, item: "dddddd", edge: "left" },
			),
		).toBeNull();
	});

	it("a pane row between items: out of its strip as a plane item, the strip of one a plane item", () => {
		const out = plan(
			{ kind: "pane", desk: DESK, item: "ssssss", plane: "e" },
			{ kind: "between", desk: DESK, index: 0 },
		);
		const desk = out?.[DESK] as Desk;
		expect(sketch(desk).slice(1)).toEqual(["aaaaaa:x", "ssssss:b", "dddddd:d"]);
		expect(desk.items[0]).toMatchObject({ kind: "plane", original: L("c"), recent: L("e") });
	});

	it("a pane row into another desk: a plane item there, its strip left as a plane item", () => {
		const out = plan(
			{ kind: "pane", desk: DESK, item: "ssssss", plane: "b" },
			{ kind: "end", desk: OTHER },
		);
		expect(sketch(out?.[OTHER]).slice(0, 2)).toEqual(["oooooo:o", { tttttt: [["p"], ["q"]] }]);
		expect(out?.[OTHER].items[2]).toMatchObject({ kind: "plane", original: L("b") });
		expect(out?.[DESK].items[1]).toEqual(pi("ssssss", "c", L("e")));
	});

	it("a pane onto a plane item: a strip, the pane keeping its links", () => {
		const out = plan(
			{ kind: "pane", desk: DESK, item: "ssssss", plane: "e" },
			{ kind: "onto", desk: DESK, item: "dddddd", edge: "right" },
		);
		expect(sketch(out?.[DESK])).toEqual(["aaaaaa:x", "ssssss:b", { dddddd: [["d"], ["e"]] }]);
	});

	it("a pane inside its own strip: moved", () => {
		const out = plan(
			{ kind: "pane", desk: DESK, item: "ssssss", plane: "b" },
			{ kind: "strip", desk: DESK, item: "ssssss", drop: { at: 2 } },
		);
		expect(sketch(out?.[DESK])[1]).toEqual({ ssssss: [["e"], ["b"]] });
		expect(
			plan(
				{ kind: "pane", desk: DESK, item: "ssssss", plane: "b" },
				{ kind: "strip", desk: DESK, item: "ssssss", drop: { at: 0 } },
			),
		).toBeNull();
	});

	it("a pane inside another desk's strip: a pane there, both desks written", () => {
		const out = plan(
			{ kind: "pane", desk: OTHER, item: "tttttt", plane: "q" },
			{ kind: "strip", desk: DESK, item: "ssssss", drop: { plane: "b", edge: "top" } },
		);
		expect(sketch(out?.[DESK])[1]).toEqual({ ssssss: [["q", "b"], ["e"]] });
		expect(sketch(out?.[OTHER])).toEqual(["oooooo:o", "tttttt:p"]);
	});

	it("unknown desks, items or panes: nothing", () => {
		expect(plan({ kind: "plane", link: L("n") }, { kind: "end", desk: "zzzzzzzz" })).toBeNull();
		expect(
			plan({ kind: "item", desk: DESK, item: "zzzzzz" }, { kind: "end", desk: OTHER }),
		).toBeNull();
		expect(
			plan({ kind: "pane", desk: DESK, item: "ssssss", plane: "zz" }, { kind: "end", desk: OTHER }),
		).toBeNull();
	});
});

describe("dropOn", () => {
	beforeEach(() => {
		resetRouter();
		setRoles({ home: "p_home" });
		setDesks(world());
	});

	it("writes each desk the drop touches once", () => {
		const wrote: string[] = [];
		onDeskWrite((id) => wrote.push(id));
		dropOn({ kind: "item", desk: DESK, item: "aaaaaa" }, { kind: "end", desk: OTHER });
		expect(wrote.sort()).toEqual([DESK, OTHER]);
		expect(sketch(knownDesks()?.[OTHER])[2]).toBe("aaaaaa:x");
	});

	it("does nothing for a drop that changes nothing", () => {
		const wrote: string[] = [];
		onDeskWrite((id) => wrote.push(id));
		dropOn(
			{ kind: "plane", link: L("b") },
			{ kind: "strip", desk: DESK, item: "ssssss", drop: { at: 0 } },
		);
		expect(wrote).toEqual([]);
	});

	it("offers a drop only where the drag table writes something", () => {
		const strip = (drop: Drop): Target => ({ kind: "strip", desk: DESK, item: "ssssss", drop });
		const pane = { kind: "pane", desk: DESK, item: "ssssss", plane: "b" } as const;
		expect(canDrop(pane, strip({ plane: "b", edge: "left" }))).toBe(false);
		expect(canDrop(pane, strip({ plane: "e", edge: "top" }))).toBe(true);
		// A link the strip shows already, onto any of its panes.
		expect(canDrop({ kind: "plane", link: L("b") }, strip({ plane: "e", edge: "top" }))).toBe(
			false,
		);
		const item = { kind: "item", desk: DESK, item: "dddddd" } as const;
		expect(canDrop(item, { kind: "onto", desk: DESK, item: "dddddd", edge: "left" })).toBe(false);
		expect(canDrop(item, { kind: "onto", desk: DESK, item: "aaaaaa", edge: "left" })).toBe(true);
		// A strip lands only between items.
		const s = { kind: "item", desk: DESK, item: "ssssss" } as const;
		expect(canDrop(s, { kind: "onto", desk: DESK, item: "aaaaaa", edge: "left" })).toBe(false);
		expect(canDrop(s, { kind: "between", desk: OTHER, index: 0 })).toBe(true);
		expect(canDrop(null, strip({ at: 0 }))).toBe(true);
	});

	it("focuses a pane dropped into the strip the tab shows", () => {
		window.history.replaceState(null, "", `/${DESK}/ssssss`);
		expect(currentRoute()).toMatchObject({ kind: "item", focus: "b" });
		dropOn(
			{ kind: "plane", link: L("n") },
			{ kind: "strip", desk: DESK, item: "ssssss", drop: { at: 2 } },
		);
		expect(focusedRoute()).toBe("n");
	});
});

describe("dropOnSolo", () => {
	beforeEach(() => {
		resetRouter();
		setRoles({ home: "p_home" });
		setDesks(world());
		window.history.replaceState(null, "", "/solo");
	});

	const made = () =>
		Object.entries(knownDesks() ?? {}).filter(([id]) => id !== DESK && id !== OTHER);

	it("makes a new desk of the solo plane and the dropped one, opened, the dropped one focused", () => {
		dropOnSolo({ kind: "plane", link: L("n") }, L("solo", { k: "v" }), "right");
		const [[id, desk]] = made();
		expect(desk.name).toBe("Untitled");
		expect(sketch(desk)).toEqual([{ [desk.items[0].id]: [["solo"], ["n"]] }]);
		const strip = desk.items[0] as Strip;
		expect(strip.columns[0].panes[0].original).toEqual(L("solo", { k: "v" }));
		expect(window.location.pathname).toBe(`/${id}/${desk.items[0].id}`);
		expect(focusedRoute()).toBe("n");
	});

	it("puts the dropped plane on the left for a left edge drop", () => {
		dropOnSolo({ kind: "plane", link: L("n") }, L("solo"), "left");
		const [[, desk]] = made();
		expect(sketch(desk)).toEqual([{ [desk.items[0].id]: [["n"], ["solo"]] }]);
	});

	it("moves a pane out of its strip into the new desk", () => {
		dropOnSolo({ kind: "pane", desk: DESK, item: "ssssss", plane: "b" }, L("solo"), "right");
		const [[, desk]] = made();
		expect(sketch(desk)).toEqual([{ [desk.items[0].id]: [["solo"], ["b"]] }]);
	});

	it("takes nothing that cannot sit beside it: itself, or a whole strip", () => {
		expect(canDropOnSolo({ kind: "plane", link: L("solo") }, "solo")).toBe(false);
		expect(canDropOnSolo({ kind: "item", desk: DESK, item: "ssssss" }, "solo")).toBe(false);
		expect(canDropOnSolo({ kind: "item", desk: DESK, item: "aaaaaa" }, "solo")).toBe(true);
		expect(canDropOnSolo(null, "solo")).toBe(true);
		dropOnSolo({ kind: "plane", link: L("solo") }, L("solo"), "right");
		dropOnSolo({ kind: "item", desk: DESK, item: "ssssss" }, L("solo"), "right");
		expect(made()).toEqual([]);
		expect(window.location.pathname).toBe("/solo");
	});
});
