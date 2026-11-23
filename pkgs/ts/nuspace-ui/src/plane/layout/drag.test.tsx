// Where a drag lands, read off what the panes and the sidebar draw, and what
// a drop sends from there. jsdom lays nothing out, so every box is placed by
// hand (`place`) and `elementFromPoint` answers what the test says is there.

import { tree } from "@nustackdev/ui-kit";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { panePath } from "../../pane/state";
import { cell, host, notify, render, VIEWER } from "../plane.testing";
import type { LayoutRow } from "../types";
import {
	ALREADY_HERE,
	aimAt,
	CELL_CHIP,
	dragNow,
	gapAt,
	LAYOUT_COLUMN,
	LAYOUT_PLANE,
	LAYOUT_ROW,
	LAYOUT_TAKES,
	markOf,
	NEW_COLUMN,
	NOT_A_TARGET,
	PLANE_ROW,
	SIDE_BY_SIDE,
	spotIn,
	zoneAt,
} from "./drag";

type Box = { left: number; top: number; width: number; height: number };

/** Lay `el` out at `box`, as a browser would have. */
function place(el: Element, box: Box): Element {
	el.getBoundingClientRect = () =>
		({ ...box, right: box.left + box.width, bottom: box.top + box.height }) as DOMRect;
	return el;
}

function div(attrs: Record<string, string>, box: Box, ...kids: Element[]): HTMLElement {
	const el = document.createElement("div");
	for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
	el.append(...kids);
	place(el, box);
	return el;
}

/** A cell's row at `top`, `height` tall, across `left`..`left + width`, its box inset by the gutters. */
function cellRow(id: string, left: number, width: number, top: number, alone = false): HTMLElement {
	const body = div(
		{ "data-cell-body": "" },
		{ left: left + 50, top, width: width - 100, height: 40 },
	);
	const attrs: Record<string, string> = { "data-cell": id };
	if (alone) attrs[LAYOUT_ROW] = id;
	return div(attrs, { left, top, width, height: 40 }, body);
}

// a, rows 0..40  |  strip [b, c] [d], 50..150 (named b)  |  e, 160..200
// Every row 400 wide; the strip's columns 200 each.
const L: LayoutRow[] = [
	{ kind: "cell", cell: "a" },
	{
		kind: "strip",
		columns: [
			{ cells: ["b", "c"], share: 0.5 },
			{ cells: ["d"], share: 0.5 },
		],
	},
	{ kind: "cell", cell: "e" },
];

function planeDom(plane: string, takes = true): HTMLElement {
	const strip = div(
		{ [LAYOUT_ROW]: "b" },
		{ left: 0, top: 50, width: 400, height: 100 },
		div(
			{ [LAYOUT_COLUMN]: "0" },
			{ left: 0, top: 50, width: 200, height: 100 },
			cellRow("b", 0, 200, 55),
			cellRow("c", 0, 200, 100),
		),
		div(
			{ [LAYOUT_COLUMN]: "1" },
			{ left: 200, top: 50, width: 200, height: 100 },
			cellRow("d", 200, 200, 55),
		),
	);
	const attrs: Record<string, string> = { [LAYOUT_PLANE]: plane };
	if (takes) attrs[LAYOUT_TAKES] = "";
	return div(
		attrs,
		{ left: 0, top: 0, width: 400, height: 220 },
		cellRow("a", 0, 400, 0, true),
		strip,
		cellRow("e", 0, 400, 160, true),
	);
}

const both = true;

describe("geometry", () => {
	const boxes = [
		{ left: 0, top: 0, width: 10, height: 40 },
		{ left: 0, top: 50, width: 10, height: 40 },
	];

	it("picks the gap before the first item whose middle is under the point", () => {
		expect(gapAt(boxes, -5)).toBe(0);
		expect(gapAt(boxes, 19)).toBe(0);
		expect(gapAt(boxes, 21)).toBe(1);
		expect(gapAt(boxes, 80)).toBe(2);
	});

	it("skips what is hidden, which has no height", () => {
		expect(gapAt([{ left: 0, top: 0, width: 0, height: 0 }, ...boxes], 10)).toBe(1);
	});

	it("reads a side quarter only when sides are offered", () => {
		const b = { left: 0, top: 0, width: 100, height: 40 };
		expect(zoneAt(b, 10, 5, true)).toBe("left");
		expect(zoneAt(b, 90, 5, true)).toBe("right");
		expect(zoneAt(b, 50, 5, true)).toBe("top");
		expect(zoneAt(b, 50, 30, true)).toBe("bottom");
		expect(zoneAt(b, 10, 30, false)).toBe("bottom");
	});
});

describe("the spot under the pointer in a pane", () => {
	const root = planeDom("p");

	it("is a gap above, between and under the items", () => {
		expect(spotIn(root, "p", 200, -10, both)).toEqual({ kind: "gap", plane: "p", index: 0 });
		expect(spotIn(root, "p", 200, 45, both)).toEqual({ kind: "gap", plane: "p", index: 1 });
		expect(spotIn(root, "p", 200, 155, both)).toEqual({ kind: "gap", plane: "p", index: 2 });
		expect(spotIn(root, "p", 200, 300, both)).toEqual({ kind: "gap", plane: "p", index: 3 });
	});

	it("is the gap above or under a cell alone, by its halves", () => {
		expect(spotIn(root, "p", 200, 10, both)).toEqual({ kind: "gap", plane: "p", index: 0 });
		expect(spotIn(root, "p", 200, 30, both)).toEqual({ kind: "gap", plane: "p", index: 1 });
	});

	it("is beside a cell alone on its box's side quarters, when sides are offered", () => {
		expect(spotIn(root, "p", 60, 10, both)).toEqual({
			kind: "side",
			plane: "p",
			cell: "a",
			side: "left",
		});
		expect(spotIn(root, "p", 340, 10, both)).toEqual({
			kind: "side",
			plane: "p",
			cell: "a",
			side: "right",
		});
		expect(spotIn(root, "p", 60, 10, false)).toEqual({
			kind: "gap",
			plane: "p",
			index: 0,
		});
	});

	it("is the gap above or under a strip on its edges", () => {
		expect(spotIn(root, "p", 100, 52, both)).toEqual({ kind: "gap", plane: "p", index: 1 });
		expect(spotIn(root, "p", 100, 147, both)).toEqual({ kind: "gap", plane: "p", index: 2 });
	});

	it("is a spot in a strip's column, above or under a cell, or the column's end", () => {
		const col = (column: number, index: number) => ({
			kind: "column",
			plane: "p",
			row: "b",
			column,
			index,
		});
		expect(spotIn(root, "p", 100, 60, both)).toEqual(col(0, 0));
		expect(spotIn(root, "p", 100, 90, both)).toEqual(col(0, 1));
		expect(spotIn(root, "p", 100, 130, both)).toEqual(col(0, 2));
		expect(spotIn(root, "p", 300, 60, both)).toEqual(col(1, 0));
		expect(spotIn(root, "p", 300, 120, both)).toEqual(col(1, 1));
	});

	it("is beside a cell of a strip on its box's side quarters", () => {
		expect(spotIn(root, "p", 55, 60, both)).toEqual({
			kind: "side",
			plane: "p",
			cell: "b",
			side: "left",
		});
		expect(spotIn(root, "p", 345, 60, both)).toEqual({
			kind: "side",
			plane: "p",
			cell: "d",
			side: "right",
		});
	});
});

describe("the mark a spot draws", () => {
	it("is a line above the item it lands before, or under the last", () => {
		expect(markOf({ kind: "gap", plane: "p", index: 0 }, L)).toEqual({ kind: "above", cell: "a" });
		expect(markOf({ kind: "gap", plane: "p", index: 1 }, L)).toEqual({ kind: "strip", row: "b" });
		expect(markOf({ kind: "gap", plane: "p", index: 3 }, L)).toEqual({ kind: "end" });
	});

	it("is a line down a cell's side, saying what it makes", () => {
		expect(markOf({ kind: "side", plane: "p", cell: "a", side: "left" }, L)).toEqual({
			kind: "left",
			cell: "a",
			hint: SIDE_BY_SIDE,
		});
		expect(markOf({ kind: "side", plane: "p", cell: "d", side: "right" }, L)).toEqual({
			kind: "right",
			cell: "d",
			hint: NEW_COLUMN,
		});
	});

	it("is a line above a column's cell, or under its last", () => {
		const col = (column: number, index: number) => ({
			kind: "column" as const,
			plane: "p",
			row: "b",
			column,
			index,
		});
		expect(markOf(col(0, 1), L)).toEqual({ kind: "above", cell: "c" });
		expect(markOf(col(0, 2), L)).toEqual({ kind: "below", cell: "c" });
		expect(markOf(col(1, 1), L)).toEqual({ kind: "below", cell: "d" });
	});

	it("is none on a pane for the sidebar's end", () => {
		expect(markOf({ kind: "end", plane: "p" }, L)).toBeNull();
	});
});

// -- Across panes and the sidebar -------------------------------------------

const Q: LayoutRow[] = [{ kind: "cell", cell: "x" }];

function seat(plane: string, props: Record<string, unknown>) {
	const path = panePath(VIEWER, plane);
	tree.getState().write(path.map((s) => [s, null]));
	tree.getState().setProps(path, props);
}

describe("aiming across panes and onto the sidebar", () => {
	let under: Element | null = null;
	const was = document.elementFromPoint;

	beforeEach(() => {
		document.elementFromPoint = () => under;
		seat("p1", { layout: L, targets: [{ id: "p2", title: "Two", icon: "" }] });
		seat("p2", { layout: Q });
	});

	afterEach(() => {
		document.elementFromPoint = was;
		tree.getState().remove(VIEWER);
		document.body.replaceChildren();
		under = null;
	});

	function pane(plane: string, takes = true): HTMLElement {
		const section = document.createElement("section");
		section.dataset.pane = plane;
		const root = planeDom(plane, takes);
		section.append(root);
		document.body.append(section);
		return root;
	}

	function sidebarRow(plane: string): HTMLElement {
		const row = div({ [PLANE_ROW]: plane }, { left: 0, top: 0, width: 200, height: 28 });
		const label = document.createElement("span");
		row.append(label);
		document.body.append(row);
		return label;
	}

	const a = { kind: "cell" as const, plane: "p1", cell: "a" };

	it("within its own pane, aims at a side and sends the strip it makes", () => {
		under = pane("p1").querySelector('[data-cell="e"] [data-cell-body]');
		const aim = aimAt(a, VIEWER, 340, 170);
		expect(aim?.spot).toEqual({ kind: "side", plane: "p1", cell: "e", side: "right" });
		expect(aim?.op?.op).toBe("layout.set");
	});

	it("onto another pane, transfers at the gap there with that plane's rows", () => {
		under = pane("p2").querySelector('[data-cell="a"]');
		const aim = aimAt(a, VIEWER, 200, 30);
		expect(aim?.spot).toEqual({ kind: "gap", plane: "p2", index: 1 });
		expect(aim?.op).toEqual({
			op: "layout.transfer",
			args: {
				cell_id: "a",
				plane_id: "p2",
				rows: [
					{ kind: "cell", cell: "x" },
					{ kind: "cell", cell: "a" },
				],
			},
		});
	});

	it("onto another pane beside a cell there, makes a strip with it there", () => {
		// p2 draws one row: x, on the same boxes as p1's a.
		const root = pane("p2");
		root.replaceChildren(cellRow("x", 0, 400, 0, true));
		under = root.querySelector('[data-cell="x"] [data-cell-body]');
		const aim = aimAt(a, VIEWER, 60, 10);
		expect(aim?.spot).toEqual({ kind: "side", plane: "p2", cell: "x", side: "left" });
		expect(aim?.op).toEqual({
			op: "layout.transfer",
			args: {
				cell_id: "a",
				plane_id: "p2",
				rows: [
					{
						kind: "strip",
						columns: [
							{ cells: ["a"], share: 0.5 },
							{ cells: ["x"], share: 0.5 },
						],
					},
				],
			},
		});
	});

	it("onto a pane whose plane takes no cell (read-only, system), aims at nothing", () => {
		under = pane("p2", false).querySelector('[data-cell="a"]');
		expect(aimAt(a, VIEWER, 200, 10)).toBeNull();
	});

	it("onto a sidebar row of a target, transfers to that plane's end", () => {
		under = sidebarRow("p2");
		expect(aimAt(a, VIEWER, 10, 10)).toEqual({
			spot: { kind: "end", plane: "p2" },
			op: { op: "cell.transfer", args: { cell_id: "a", plane_id: "p2" } },
			refused: null,
		});
	});

	it("onto its own plane's row, or one not a target, is refused and sends nothing", () => {
		under = sidebarRow("p1");
		expect(aimAt(a, VIEWER, 10, 10)).toMatchObject({ op: null, refused: ALREADY_HERE });
		under = sidebarRow("p9");
		expect(aimAt(a, VIEWER, 10, 10)).toMatchObject({ op: null, refused: NOT_A_TARGET });
	});

	it("onto a sidebar row before the targets are answered, aims at nothing yet", () => {
		seat("p1", { layout: L, targets: null });
		under = sidebarRow("p2");
		expect(aimAt(a, VIEWER, 10, 10)).toBeNull();
	});
});

// -- A drag, end to end, on a drawn plane -------------------------------------

describe("a drag off a cell's grip", () => {
	const was = document.elementFromPoint;
	let under: Element | null = null;

	beforeEach(() => {
		document.elementFromPoint = () => under;
	});
	afterEach(() => {
		document.elementFromPoint = was;
	});

	const at = (type: string, x: number, y: number) =>
		new MouseEvent(type, { bubbles: true, button: 0, clientX: x, clientY: y });

	function drawn(layout: LayoutRow[]) {
		seat("p1", { layout });
		render([cell("a"), cell("b"), cell("c")], { layout });
		host.dataset.pane = "p1";
	}

	it("draws a strip's columns, each with its cells", () => {
		drawn([
			{ kind: "cell", cell: "a" },
			{
				kind: "strip",
				columns: [
					{ cells: ["b"], share: 0.4 },
					{ cells: ["c"], share: 0.6 },
				],
			},
		]);
		const columns = [...host.querySelectorAll(`[${LAYOUT_ROW}="b"] [${LAYOUT_COLUMN}]`)];
		expect(
			columns.map((c) =>
				[...c.querySelectorAll("[data-cell]")].map((r) => r.getAttribute("data-cell")),
			),
		).toEqual([["b"], ["c"]]);
		expect(host.querySelector(`[data-cell="a"]`)?.getAttribute(LAYOUT_ROW)).toBe("a");
		expect(host.querySelector(`[data-cell="b"]`)?.hasAttribute(LAYOUT_ROW)).toBe(false);
	});

	it("asks for targets as it starts, marks the drop, and sends the op on release", () => {
		const layout: LayoutRow[] = [
			{ kind: "cell", cell: "a" },
			{ kind: "cell", cell: "b" },
			{ kind: "cell", cell: "c" },
		];
		drawn(layout);
		const row = (id: string) => host.querySelector(`[data-cell="${id}"]`) as HTMLElement;
		place(row("a"), { left: 0, top: 0, width: 400, height: 40 });
		place(row("b"), { left: 0, top: 50, width: 400, height: 40 });
		place(row("c"), { left: 0, top: 100, width: 400, height: 40 });
		for (const id of ["a", "b", "c"]) {
			const body = row(id).querySelector("[data-cell-body]") as HTMLElement;
			place(body, { ...row(id).getBoundingClientRect(), left: 50, width: 300 });
		}
		notify.mockClear();
		const grip = row("c").querySelector("[data-cell-grip]") as HTMLElement;
		act(() => {
			grip.dispatchEvent(at("pointerdown", 0, 110));
		});
		// Over a's right quarter: beside it.
		under = row("a").querySelector("[data-cell-body]");
		act(() => {
			window.dispatchEvent(at("pointermove", 330, 10));
		});
		expect(notify.mock.calls[0]).toEqual(["cell.targets", {}]);
		// The chip rides under the pointer, saying what is dragged.
		const chip = () => document.querySelector<HTMLElement>("[data-drag-chip]");
		expect(chip()?.textContent).toBe(CELL_CHIP);
		expect([chip()?.style.left, chip()?.style.top]).toEqual(["316px", "-4px"]);
		expect(row("a").textContent).toContain(SIDE_BY_SIDE);
		act(() => {
			window.dispatchEvent(at("pointerup", 330, 10));
		});
		expect(notify.mock.calls.at(-1)).toEqual([
			"layout.set",
			{
				rows: [
					{
						kind: "strip",
						columns: [
							{ cells: ["a"], share: 0.5 },
							{ cells: ["c"], share: 0.5 },
						],
					},
					{ kind: "cell", cell: "b" },
				],
			},
		]);
		expect(row("a").textContent).not.toContain(SIDE_BY_SIDE);
		expect(chip()).toBeNull();
	});

	it("a press that never travels opens the cell's menu and sends nothing", () => {
		drawn([
			{ kind: "cell", cell: "a" },
			{ kind: "cell", cell: "b" },
			{ kind: "cell", cell: "c" },
		]);
		notify.mockClear();
		const grip = host.querySelector('[data-cell="b"] [data-cell-grip]') as HTMLElement;
		act(() => {
			grip.dispatchEvent(at("pointerdown", 0, 0));
			window.dispatchEvent(at("pointerup", 1, 1));
		});
		expect(notify).not.toHaveBeenCalled();
		expect(grip.getAttribute("data-menu")).toBe("open");
	});

	it("aims again when what is under the pointer scrolls", () => {
		drawn([
			{ kind: "cell", cell: "a" },
			{ kind: "cell", cell: "b" },
			{ kind: "cell", cell: "c" },
		]);
		const row = (id: string) => host.querySelector(`[data-cell="${id}"]`) as HTMLElement;
		/** Lay the rows out from `top`, 50 apart, each cell's box with them. */
		const lay = (top: number) =>
			["a", "b", "c"].forEach((id, i) => {
				const box = { left: 0, top: top + 50 * i, width: 400, height: 40 };
				place(row(id), box);
				place(row(id).querySelector("[data-cell-body]") as Element, {
					...box,
					left: 50,
					width: 300,
				});
			});
		lay(0);
		const grip = row("c").querySelector("[data-cell-grip]") as HTMLElement;
		under = row("a");
		act(() => {
			grip.dispatchEvent(at("pointerdown", 0, 110));
			window.dispatchEvent(at("pointermove", 200, 5));
		});
		expect(dragNow()?.aim?.spot).toEqual({ kind: "gap", plane: "p1", index: 0 });
		// The body scrolls 50 down under a still pointer: b is under it now.
		lay(-50);
		under = row("b");
		act(() => {
			host.dispatchEvent(new Event("scroll"));
		});
		expect(dragNow()?.aim?.spot).toEqual({ kind: "gap", plane: "p1", index: 1 });
		act(() => {
			window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
		});
		// Gone with the drag: a scroll after it aims nothing.
		act(() => {
			host.dispatchEvent(new Event("scroll"));
		});
		expect(dragNow()).toBeNull();
	});

	it("Escape drops the drag, sending nothing", () => {
		drawn([
			{ kind: "cell", cell: "a" },
			{ kind: "cell", cell: "b" },
			{ kind: "cell", cell: "c" },
		]);
		const row = (id: string) => host.querySelector(`[data-cell="${id}"]`) as HTMLElement;
		place(row("a"), { left: 0, top: 0, width: 400, height: 40 });
		const grip = row("c").querySelector("[data-cell-grip]") as HTMLElement;
		under = row("a");
		act(() => {
			grip.dispatchEvent(at("pointerdown", 0, 110));
			window.dispatchEvent(at("pointermove", 200, 5));
		});
		notify.mockClear();
		act(() => {
			window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
			window.dispatchEvent(at("pointerup", 200, 5));
		});
		expect(notify).not.toHaveBeenCalled();
		expect(document.querySelector("[data-drag-chip]")).toBeNull();
	});
});
