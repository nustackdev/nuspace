// The sidebar screen's pure parts: the rows a desk folder draws on the phone,
// and the actions a plane row's long-press offers.
//
// A desk folder on the phone mirrors desktop's (../../sidebar/folders.ts
// `folderRows`): plane items, `Strip` rows, `Column` groups for a column of
// 2+ panes, pane rows, folded the same way. Every row but a plane item opens
// the desk screen's pager on a pane: a strip on its first, a column on its
// top one, a pane on itself. The page is the pager's own (../desk/model.ts),
// so the row and the pager agree on where a tap lands.

import type { Desk } from "../../desk/model";
import { shownLinks } from "../../desk/model";
import { type FolderRow, folderRows, rowDepth } from "../../sidebar/folders";
import { canDelete } from "../../sidebar/remove";
import type { PlaneTree } from "../../sidebar/types";
import { pageOf, pagesOf } from "../desk/model";

/** One row of a desk folder as the phone draws it. */
export type DeskRow = {
	row: FolderRow;
	/** Under the folder title: one lane in, then desktop's depth. */
	depth: number;
	/** The plane a tap focuses in a strip; "" for a plane item (it opens as itself). */
	pane: string;
	/** The pager's page that plane is on; 0 for a plane item. */
	page: number;
};

/** The rows desk `id` draws on the phone, given what is folded. */
export function deskRows(id: string, desk: Desk, folded: Set<string>): DeskRow[] {
	return folderRows(id, desk, folded).map((row) => {
		const depth = rowDepth(row) + 1;
		if (row.kind === "plane") return { row, depth, pane: "", page: 0 };
		const item = desk.items.find((i) => i.id === row.item);
		const pages = item ? pagesOf(item) : [];
		const pane =
			row.kind === "pane" ? row.plane : row.kind === "column" ? row.planes[0] : pages[0]?.plane;
		return { row, depth, pane: pane ?? "", page: pageOf(pages, pane ?? "") };
	});
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
