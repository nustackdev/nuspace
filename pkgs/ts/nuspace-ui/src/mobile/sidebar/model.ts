// The sidebar screen's pure parts: the rows a desk folder draws on the phone,
// and the actions a plane row's long-press offers.
//
// A desk folder on the phone is one row per item, never the strip's columns
// and panes: tapping an item opens it, and the desk screen pages through its
// panes. A strip row is named by its first pane (reading order: column by
// column, top to bottom) and says how many panes it holds.

import type { Desk, Links } from "../../desk/model";
import { shown } from "../../desk/model";
import { canDelete } from "../../sidebar/remove";
import type { PlaneTree } from "../../sidebar/types";

/** One desk item as the phone's folder draws it. */
export type DeskRow = {
	/** The item's id: what the row opens. */
	item: string;
	/** The plane that names the row: the plane item's, a strip's first pane's. */
	plane: string;
	/** Panes in the item: 1 for a plane item. */
	panes: number;
	strip: boolean;
};

/** The rows desk `desk` draws on the phone, in item order. */
export function deskRows(desk: Desk): DeskRow[] {
	return desk.items.map((item) => {
		if (item.kind === "plane") {
			return { item: item.id, plane: shown(item).plane, panes: 1, strip: false };
		}
		const panes: Links[] = item.columns.flatMap((col) => col.panes);
		return {
			item: item.id,
			plane: panes[0] ? shown(panes[0]).plane : "",
			panes: panes.length,
			strip: true,
		};
	});
}

/** Every plane the folders name, for their looks. */
export function deskPlanes(desks: Desk[]): string[] {
	const out = new Set<string>();
	for (const desk of desks) for (const row of deskRows(desk)) if (row.plane) out.add(row.plane);
	return [...out];
}

/** What a long-press on a plane row offers. */
export type PlaneAction = "rename" | "inside" | "delete";

/** The actions plane `id` offers, in sheet order: delete only where the server takes one. */
export function planeActions(tree: PlaneTree, id: string): PlaneAction[] {
	if (!tree[id]) return [];
	return canDelete(tree, id) ? ["rename", "inside", "delete"] : ["rename", "inside"];
}

/** A strip row's note: how many panes. */
export function paneCount(n: number): string {
	return n === 1 ? "1 pane" : `${n} panes`;
}
