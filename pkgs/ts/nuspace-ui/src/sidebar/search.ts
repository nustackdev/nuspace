// Whether the search popup is open, and what it keeps between opens.
//
// Two things open it, the sidebar's search entry and cmd/ctrl+K from anywhere
// in the window, so it is a module level store like ./add.ts rather than a
// hook's own state. The one popup lives with the rail, which holds the
// searchable list.
//
// Which kinds are ticked outlives a close, for the tab's life: the next search
// looks where the last one did. Everything starts ticked.

import type { SetStateAction } from "react";
import { useCallback, useSyncExternalStore } from "react";

/** The search Plane's id, fixed by the host: where a search is shown. */
export const SEARCH_PLANE = "search";

/** The popup's own kind, beside the snippets: Plane titles. */
export const TITLES = "";

/** The shortcut, for the entry's hint. */
export const SEARCH_SHORTCUT =
	typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent) ? "⌘K" : "Ctrl+K";

let open = false;
/** Kinds unticked, by name: a kind not here is ticked. `TITLES` for titles. */
let off: ReadonlySet<string> = new Set();
const subscribers = new Set<() => void>();

function emit(): void {
	for (const cb of subscribers) cb();
}

function subscribe(cb: () => void): () => void {
	subscribers.add(cb);
	return () => subscribers.delete(cb);
}

export function openSearch(): void {
	if (open) return;
	open = true;
	emit();
}

export function closeSearch(): void {
	if (!open) return;
	open = false;
	emit();
}

export function useSearchOpen(): boolean {
	return useSyncExternalStore(
		subscribe,
		() => open,
		() => open,
	);
}

/** Tick or untick one kind. */
export function toggleKind(name: string): void {
	const next = new Set(off);
	if (next.has(name)) next.delete(name);
	else next.add(name);
	off = next;
	emit();
}

/** The kinds unticked. A new set on every change, so it is a stable snapshot. */
export function useUnticked(): ReadonlySet<string> {
	return useSyncExternalStore(
		subscribe,
		() => off,
		() => off,
	);
}

/**
 * The popup's open state as a React setter, for the kit's
 * `useCommandPaletteHotkey`, which flips it on cmd/ctrl+K.
 */
export function useSearchSetter(): (value: SetStateAction<boolean>) => void {
	return useCallback((value: SetStateAction<boolean>) => {
		const next = typeof value === "function" ? value(open) : value;
		if (next) openSearch();
		else closeSearch();
	}, []);
}
