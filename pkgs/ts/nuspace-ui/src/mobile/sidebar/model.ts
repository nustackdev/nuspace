// The sidebar screen's pure parts: the rows a desk folder draws on the phone,
// and the actions a plane row's long-press offers.
//
// A desk folder on the phone is one level: a row per desk item, in the
// desk's order. A plane item opens as itself. A strip is one row naming its
// panes' planes in reading order, the pager's own (../desk/model.ts
// `pagesOf`), and opens the pager on the first of them. Desktop's Strip,
// Column and pane rows (../../sidebar/folders.ts) stay desktop's.

import type { Desk, Item } from "../../desk/model";
import { shownLinks } from "../../desk/model";
import { canDelete } from "../../sidebar/remove";
import type { PlaneTree } from "../../sidebar/types";
import { pagesOf } from "../desk/model";

/** One row of a desk folder as the phone draws it: one desk item. */
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

/** The most plane icons a strip row stacks. */
export const STACK_MAX = 3;

/** The icons a strip row stacks, in order, and how many more it counts as +N. */
export function stackOf(planes: string[]): { shown: string[]; more: number } {
	return { shown: planes.slice(0, STACK_MAX), more: Math.max(0, planes.length - STACK_MAX) };
}

/** A strip row's label: "3 planes". */
export function stripLabel(count: number): string {
	return count === 1 ? "1 plane" : `${count} planes`;
}

/** Every plane the folders can name, for their looks. */
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
