// Where an Add plane request goes, and the rename that follows it.
//
// Three places open the same popup: the sidebar header's `+` (a Plane at the
// top), a row's hover `+` (a child of that row) and a pane's `...` menu (a
// child of that pane's Plane). The pane is in the Viewer, not the sidebar, so
// the request is a module level store like the router rather than a prop, and
// the one popup lives with the rail, which holds the registered list.
//
// After a create, the new Plane's row does not exist until the server reships
// the tree. `pendingRename` holds its id until the rail sees the row and puts
// it in rename mode.

import { useSyncExternalStore } from "react";

export type AddRequest = {
	/** Where the new Plane hangs: a Plane id, or `ROOT_ID`. */
	parent: string;
	/** The pane to open it in. The focused pane when left out. */
	pane?: string;
};

let request: AddRequest | null = null;
let pending = "";
const subscribers = new Set<() => void>();

function emit(): void {
	for (const cb of subscribers) cb();
}

function subscribe(cb: () => void): () => void {
	subscribers.add(cb);
	return () => subscribers.delete(cb);
}

/** Open the popup for `req`. */
export function openAddPlane(req: AddRequest): void {
	request = req;
	emit();
}

/** Close it without making anything. */
export function closeAddPlane(): void {
	if (!request) return;
	request = null;
	emit();
}

/** The open request, null while the popup is shut. */
export function useAddRequest(): AddRequest | null {
	return useSyncExternalStore(
		subscribe,
		() => request,
		() => request,
	);
}

/** Mark a new Plane for rename once its row lands. */
export function renameWhenListed(planeId: string): void {
	pending = planeId;
	emit();
}

/** Drop the mark, once the rename started. */
export function clearPendingRename(): void {
	if (!pending) return;
	pending = "";
	emit();
}

/** The Plane waiting for its row, "" when none is. */
export function usePendingRename(): string {
	return useSyncExternalStore(
		subscribe,
		() => pending,
		() => pending,
	);
}
