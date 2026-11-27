// The sidebar screen's pure parts: the rows a desk section draws on the
// phone, a strip row's composite icon and the +N of its label, and the
// actions a plane row's long-press offers.
//
// A desk section on the phone is one level: a row per desk item, in the
// desk's order. A plane item opens as itself. A strip is one row naming its
// panes' planes in reading order, the pager's own (../desk/model.ts
// `pagesOf`), and opens the pager on the first of them. Desktop's Strip,
// Column and pane rows (../../sidebar/folders.ts) stay desktop's.

import type { Desk, Item } from "../../desk/model";
import { shownLinks } from "../../desk/model";
import { canDelete } from "../../sidebar/remove";
import type { PlaneTree } from "../../sidebar/types";
import { pagesOf } from "../desk/model";

/** One row of a desk section as the phone draws it: one desk item. */
export type DeskRow = {
	item: Item;
	/** The planes the item shows, in the pager's order: one for a plane item. */
	planes: string[];
	/** The plane a tap focuses in a strip, the pager's first page; "" for a plane item. */
	pane: string;
};

/** The rows desk `desk` draws on the phone, one per item. */
export function deskRows(desk: Desk): DeskRow[] {
	return desk.items.map((item) => {
		const planes = pagesOf(item).map((p) => p.plane);
		return { item, planes, pane: item.kind === "strip" ? (planes[0] ?? "") : "" };
	});
}

// -- A strip row's lead ---------------------------------------------------------

/** The box every row's icon takes, in px. A strip's composite fills it, never more. */
export const ICON_BOX = 20;

/** One cell of a composite icon, in px inside the box. */
export type Cell = { x: number; y: number; w: number; h: number };

/**
 * A strip's composite icon for `count` planes: the cells, the first `shown`
 * planes' icons in them in order, and `more` planes counted in the last
 * cell as +N. All on whole pixels, so it stays crisp at 2x and 3x.
 *
 *   1   the one icon, the whole box
 *   2   two halves, side by side
 *   3   a triad: one top centre, two under it
 *   4   a 2x2 grid
 *   5+  a 2x2 grid, its last cell +N: the planes past the first three
 */
export function compositeOf(count: number): { cells: Cell[]; shown: number; more: number } {
	const b = ICON_BOX;
	const h = b / 2;
	const grid = [
		{ x: 0, y: 0, w: h, h },
		{ x: h, y: 0, w: h, h },
		{ x: 0, y: h, w: h, h },
		{ x: h, y: h, w: h, h },
	];
	if (count <= 0) return { cells: [], shown: 0, more: 0 };
	if (count === 1) return { cells: [{ x: 0, y: 0, w: b, h: b }], shown: 1, more: 0 };
	if (count === 2)
		return {
			cells: [
				{ x: 0, y: 0, w: h, h: b },
				{ x: h, y: 0, w: h, h: b },
			],
			shown: 2,
			more: 0,
		};
	if (count === 3)
		return { cells: [{ x: h / 2, y: 0, w: h, h }, grid[2], grid[3]], shown: 3, more: 0 };
	if (count === 4) return { cells: grid, shown: 4, more: 0 };
	return { cells: grid, shown: 3, more: count - 3 };
}

// -- A strip row's label --------------------------------------------------------

/** Between two titles in a strip row's label. */
export const TITLE_SEP = ", ";

/**
 * How many of a strip's titles its one-line label cannot show in full: the
 * +N after the label. `ends` is where each title's text ends, from the
 * label's start, laid out on one line; `width` the room the label has;
 * `ellipsis` the width of the "…" the line ends in when cut; `more(n)` the
 * width "+n" takes after it. 0 when every title fits; otherwise the most
 * titles that fit in full before the "…" and the +N, the rest counted.
 */
export function hiddenTitles(
	ends: readonly number[],
	width: number,
	ellipsis: number,
	more: (n: number) => number,
): number {
	const n = ends.length;
	// Half a pixel of slack: layout rounds.
	if (!n || ends[n - 1] <= width + 0.5) return 0;
	for (let shown = n - 1; shown > 0; shown--) {
		if (ends[shown - 1] <= width - more(n - shown) - ellipsis + 0.5) return n - shown;
	}
	return n;
}

/** Every plane the desk sections can name, for their looks. */
export function deskPlanes(desks: Desk[]): string[] {
	const out = new Set<string>();
	for (const desk of desks)
		for (const item of desk.items) for (const link of shownLinks(item)) out.add(link.plane);
	return [...out];
}

/** What a long-press on a plane row offers. */
export type PlaneAction = "rename" | "inside" | "delete";

/** The actions plane `id` offers, in sheet order: delete only where the server takes one. */
export function planeActions(tree: PlaneTree, id: string): PlaneAction[] {
	if (!tree[id]) return [];
	return canDelete(tree, id) ? ["rename", "inside", "delete"] : ["rename", "inside"];
}
