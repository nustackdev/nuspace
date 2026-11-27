// The sidebar screen's logic: open as a history entry, a desk's rows on the
// phone and the pages they open, a strip row's composite icon and +N, what a plane's long-press offers, the add
// sheet's groups.

import { History } from "@nustackdev/ui-kit";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { Desk, Item } from "../../desk/model";
import type { PlaneTree, TreeRow } from "../../sidebar/types";
import { pageOf, pagesOf } from "../desk/model";
import { addGroups } from "./AddPlaneSheet";
import { compositeOf, deskPlanes, deskRows, hiddenTitles, ICON_BOX, planeActions } from "./model";
import {
	isSidebarEntry,
	leaveThen,
	markState,
	openSidebar,
	SIDEBAR_STATE,
	settleSidebar,
} from "./open";

const link = (plane: string) => ({ original: { plane, params: {} } });

describe("deskRows", () => {
	// Two columns: logs over errors, then alerts. Pages in reading order: logs, errors, alerts.
	const desk: Desk = {
		name: "Ops",
		items: [
			{ id: "item01", kind: "plane", ...link("deploys") },
			{
				id: "item02",
				kind: "strip",
				columns: [
					{
						panes: [
							{ share: 1, ...link("logs") },
							{ share: 1, ...link("errors") },
						],
					},
					{ panes: [{ share: 1, ...link("alerts") }] },
				],
			},
		],
	};
	const strip = desk.items[1] as Extract<Item, { kind: "strip" }>;

	it("draws one row per item, a strip as one row", () => {
		expect(deskRows(desk).map((r) => [r.item.id, r.item.kind])).toEqual([
			["item01", "plane"],
			["item02", "strip"],
		]);
	});

	it("names a strip's planes in the pager's order, column by column", () => {
		const [plane, row] = deskRows(desk);
		expect(plane.planes).toEqual(["deploys"]);
		expect(row.planes).toEqual(["logs", "errors", "alerts"]);
		expect(row.planes).toEqual(pagesOf(strip).map((p) => p.plane));
	});

	it("opens a strip on the pager's first page, a plane item as itself", () => {
		const [plane, row] = deskRows(desk);
		expect(plane.pane).toBe("");
		expect(row.pane).toBe("logs");
		expect(pageOf(pagesOf(strip), row.pane)).toBe(0);
	});

	it("names every plane the rows can show, for their looks", () => {
		expect(deskPlanes([desk])).toEqual(["deploys", "logs", "errors", "alerts"]);
	});
});

describe("compositeOf", () => {
	const inBox = (c: { x: number; y: number; w: number; h: number }) =>
		c.x >= 0 && c.y >= 0 && c.x + c.w <= ICON_BOX && c.y + c.h <= ICON_BOX;
	const whole = (c: { x: number; y: number; w: number; h: number }) =>
		[c.x, c.y, c.w, c.h].every(Number.isInteger);

	it("splits two planes into halves side by side", () => {
		expect(compositeOf(2)).toEqual({
			cells: [
				{ x: 0, y: 0, w: 10, h: 20 },
				{ x: 10, y: 0, w: 10, h: 20 },
			],
			shown: 2,
			more: 0,
		});
	});

	it("sets three as a triad, one top centre and two under", () => {
		expect(compositeOf(3).cells).toEqual([
			{ x: 5, y: 0, w: 10, h: 10 },
			{ x: 0, y: 10, w: 10, h: 10 },
			{ x: 10, y: 10, w: 10, h: 10 },
		]);
	});

	it("grids four two by two", () => {
		const { cells, shown, more } = compositeOf(4);
		expect(cells.map((c) => [c.x, c.y])).toEqual([
			[0, 0],
			[10, 0],
			[0, 10],
			[10, 10],
		]);
		expect([shown, more]).toEqual([4, 0]);
	});

	it("grids five and more, the last cell counting the planes past three", () => {
		expect(compositeOf(5)).toMatchObject({ shown: 3, more: 2 });
		expect(compositeOf(8)).toMatchObject({ shown: 3, more: 5 });
		expect(compositeOf(8).cells).toEqual(compositeOf(4).cells);
	});

	it("stays inside the row's icon box, on whole pixels", () => {
		for (let n = 1; n <= 9; n++) {
			const { cells, shown, more } = compositeOf(n);
			expect(cells.every(inBox)).toBe(true);
			expect(cells.every(whole)).toBe(true);
			expect(shown + more).toBe(n);
			expect(cells.length).toBe(shown + (more ? 1 : 0));
		}
	});
});

describe("hiddenTitles", () => {
	// Titles 50px wide, ", " 10px: a title ends every 60px, the last at 290.
	const ends = [50, 110, 170, 230, 290];
	const more = (n: number) => 4 + 8 * String(n).length + 6;

	it("counts nothing when every title fits", () => {
		expect(hiddenTitles(ends, 290, 8, more)).toBe(0);
		expect(hiddenTitles(ends, 400, 8, more)).toBe(0);
		expect(hiddenTitles([], 10, 8, more)).toBe(0);
	});

	it("counts the titles not fully shown before the ellipsis and the +N", () => {
		// 200 less "+3" (18) and the ellipsis (8): 174, so three titles end in it.
		expect(hiddenTitles(ends, 200, 8, more)).toBe(2);
		// 289: the last ends a pixel past it.
		expect(hiddenTitles(ends, 289, 8, more)).toBe(1);
		// 120 less 18 and 8: 94, one title.
		expect(hiddenTitles(ends, 120, 8, more)).toBe(4);
	});

	it("counts every title when none fits in full", () => {
		expect(hiddenTitles(ends, 40, 8, more)).toBe(5);
	});

	it("leaves room for a wider +N", () => {
		const wide = (n: number) => (n > 1 ? 60 : 20);
		// +1 fits after four titles (230 + 20 + 8 <= 260); no squeeze needed.
		expect(hiddenTitles(ends, 260, 8, wide)).toBe(1);
		// At 250, +1 does not fit after four; +2 (60) leaves 182: three titles.
		expect(hiddenTitles(ends, 250, 8, wide)).toBe(2);
	});
});

const row = (id: string, system = false): TreeRow => ({
	id,
	kind: "plane",
	title: id,
	parent: "space",
	children: [],
	spec: "",
	icon: "",
	system,
});

describe("planeActions", () => {
	const tree: PlaneTree = { mine: row("mine"), sys: row("sys", true) };

	it("offers rename, add inside and delete", () => {
		expect(planeActions(tree, "mine")).toEqual(["rename", "inside", "delete"]);
	});

	it("offers no delete on a system plane", () => {
		expect(planeActions(tree, "sys")).toEqual(["rename", "inside"]);
	});

	it("offers nothing for a plane the tree does not hold", () => {
		expect(planeActions(tree, "gone")).toEqual([]);
	});
});

describe("addGroups", () => {
	it("groups registered planes by package, in first-seen order", () => {
		const r = (name: string) => ({ name, label: name, group: "", icon: "", description: "" });
		const groups = addGroups([r("nuverse.notes"), r("ops.board"), r("nuverse.todo")]);
		expect(groups.map((g) => [g.pkg, g.entries.map((e) => e.name)])).toEqual([
			["nuverse", ["nuverse.notes", "nuverse.todo"]],
			["ops", ["ops.board"]],
		]);
	});
});

describe("the sidebar as a history entry", () => {
	beforeEach(() => {
		window.history.replaceState(null, "", "/p/home");
	});
	afterEach(() => {
		window.history.replaceState(null, "", "/");
	});

	it("marks state without losing what was there", () => {
		expect(markState(null, true)).toEqual({ [SIDEBAR_STATE]: true });
		expect(markState({ a: 1 }, true)).toEqual({ a: 1, [SIDEBAR_STATE]: true });
		expect(markState({ a: 1, [SIDEBAR_STATE]: true }, false)).toEqual({ a: 1 });
		expect(markState({ [SIDEBAR_STATE]: true }, false)).toBeNull();
	});

	it("opens by pushing the same url with the mark", () => {
		const before = window.history.length;
		openSidebar();
		expect(window.history.length).toBe(before + 1);
		expect(History.current().url).toBe("/p/home");
		expect(isSidebarEntry(History.current())).toBe(true);
		// Open already: no second entry.
		openSidebar();
		expect(window.history.length).toBe(before + 1);
	});

	it("leaves by going back first, then moving on", async () => {
		openSidebar();
		const moved = new Promise<string>((resolve) => {
			leaveThen(() => {
				resolve(History.current().url);
				History.push("/p/notes");
			});
		});
		// Back landed on the entry under the sidebar's, before the move.
		expect(await moved).toBe("/p/home");
		expect(isSidebarEntry(History.current())).toBe(false);
		expect(History.current().url).toBe("/p/notes");
	});

	it("moves on at once when closed", () => {
		let ran = false;
		leaveThen(() => {
			ran = true;
		});
		expect(ran).toBe(true);
	});

	it("drops the mark in place after a reload while open", () => {
		window.history.replaceState({ [SIDEBAR_STATE]: true }, "", "/p/home");
		const before = window.history.length;
		settleSidebar();
		expect(isSidebarEntry(History.current())).toBe(false);
		expect(window.history.length).toBe(before);
	});
});
