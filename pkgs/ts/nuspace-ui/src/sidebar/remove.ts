// Deleting a Plane from a sidebar row. A pane's `...` has its own delete,
// on the pane's own node, off the pane's own head (../pane/Pane.tsx).
//
// The server refuses a system Plane's delete, so the row offers none.

import { confirm } from "../core/confirm";
import { leavePlanes } from "../core/router";
import type { Notify } from "./ops";
import { subtreeOf } from "./tree";
import type { PlaneTree } from "./types";

/** Whether to offer a delete: a Plane the tree holds and that is not a system one. */
export function canDelete(tree: PlaneTree, id: string): boolean {
	const row = tree[id];
	return !!row && !row.system;
}

/**
 * Ask, then delete `id` and everything under it. A tab showing one of them
 * solo goes home (the server takes them off every desk). Replace, not push:
 * the back button should not bring back a Plane that no longer exists.
 */
export async function deletePlane(
	notify: Notify,
	tree: PlaneTree,
	id: string,
	title: string,
): Promise<void> {
	const yes = await confirm({
		title: "Delete plane",
		description: `Delete "${title}" and everything under it?`,
		action: "Delete",
	});
	if (!yes) return;
	notify("plane.delete", { plane_id: id });
	leavePlanes(subtreeOf(tree, id), true);
}
