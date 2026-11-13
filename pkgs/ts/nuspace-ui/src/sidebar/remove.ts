// Deleting a Plane from a sidebar row. A pane's `...` has its own delete,
// on the pane's own node, off the pane's own head (../pane/Pane.tsx).
//
// The server refuses a system Plane's delete, so the row offers none.
//
// Nothing here moves the tab off what went: the tree holds only open
// branches, so it cannot say what was under the Plane. Each open pane on a
// Plane that went is told it is missing and leaves by itself.

import { confirm } from "../core/confirm";
import type { Notify } from "./ops";
import type { PlaneTree } from "./types";

/** Whether to offer a delete: a Plane the tree holds and that is not a system one. */
export function canDelete(tree: PlaneTree, id: string): boolean {
	const row = tree[id];
	return !!row && !row.system;
}

/** Ask, then delete `id` and everything under it. */
export async function deletePlane(notify: Notify, id: string, title: string): Promise<void> {
	const yes = await confirm({
		title: "Delete plane",
		description: `Delete "${title}" and everything under it?`,
		action: "Delete",
	});
	if (!yes) return;
	notify("plane.delete", { plane_id: id });
}
