// Deleting a Plane: one way in, from a sidebar row or a pane's `...`.
//
// The server refuses a system Plane's delete, so neither place offers one.

import { closePanes } from "../core/router";
import { confirm } from "../shell/confirm";
import type { Notify } from "./ops";
import { subtreeOf } from "./tree";
import type { PlaneTree } from "./types";

/** Whether to offer a delete: a Plane the tree holds and that is not a system one. */
export function canDelete(tree: PlaneTree, id: string): boolean {
	const row = tree[id];
	return !!row && !row.system;
}

/**
 * Ask, then delete `id` and everything under it. Their panes go too, and
 * when none is left the router lands on "/". Replace, not push: the back
 * button should not bring back a Plane that no longer exists.
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
	closePanes(subtreeOf(tree, id), true);
}
