// Where the dock's Add cell sends its tap (./dock/ControlSheet.tsx): a
// request to add a cell to the plane on screen. A module store like
// ../sidebar/add.ts, since the dock sits in the frame and the sheet that
// answers it sits with the plane.

import { useSyncExternalStore } from "react";

let open = false;
const subscribers = new Set<() => void>();

function emit(): void {
	for (const cb of [...subscribers]) cb();
}

function subscribe(cb: () => void): () => void {
	subscribers.add(cb);
	return () => subscribers.delete(cb);
}

/** Ask for the add cell sheet. */
export function openAddCell(): void {
	if (open) return;
	open = true;
	emit();
}

/** Close it without adding anything. */
export function closeAddCell(): void {
	if (!open) return;
	open = false;
	emit();
}

/** Whether the add cell sheet is asked for. */
export function useAddCellOpen(): boolean {
	return useSyncExternalStore(
		subscribe,
		() => open,
		() => open,
	);
}
