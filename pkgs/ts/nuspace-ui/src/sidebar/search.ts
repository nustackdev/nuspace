// Whether the search popup is open, and what it keeps between opens.
//
// Two things open it, the sidebar's search entry and cmd/ctrl+K from anywhere
// in the window, so it is a module level store like ./add.ts rather than a
// hook's own state. The one popup lives with the rail, which holds the
// searchable list.
//
// Which kinds are ticked, and which groups are folded, outlive a close, for
// the tab's life: the next search looks where the last one did. Everything
// starts ticked; a group starts folded once the list is long (`FOLD_OVER`).
//
// And what the popup lists, pure: the snippets in their groups, registry order,
// and whether a set of kinds reads as ticked, unticked or partly.

import type { SetStateAction } from "react";
import { useCallback, useSyncExternalStore } from "react";
import { menuSections } from "../menu/rank";
import type { Searchable } from "./types";

/** The search Plane's id, fixed by the host: where a search is shown. */
export const SEARCH_PLANE = "search";

/** The popup's own kind, beside the snippets: Plane titles. */
export const TITLES = "";

/** The shortcut by key name, for the entry's hint; the kit `Shortcut` spells it. */
export const SEARCH_KEYS = ["mod", "K"] as const;

/** Past this many snippets, a group starts folded: the groups are the overview. */
export const FOLD_OVER = 12;

let open = false;
/** Kinds unticked, by name: a kind not here is ticked. `TITLES` for titles. */
let off: ReadonlySet<string> = new Set();
/** Groups folded or unfolded by hand, by heading. One not here takes the default. */
let folds: ReadonlyMap<string, boolean> = new Map();
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

/** Tick every kind in `names`, or untick them all: a group's box, or the All row's. */
export function setKinds(names: readonly string[], ticked: boolean): void {
	const next = new Set(off);
	for (const name of names) {
		if (ticked) next.delete(name);
		else next.add(name);
	}
	off = next;
	emit();
}

/** Fold or unfold one group. */
export function setFold(group: string, folded: boolean): void {
	const next = new Map(folds);
	next.set(group, folded);
	folds = next;
	emit();
}

/** The groups folded or unfolded by hand. A new map on every change. */
export function useFolds(): ReadonlyMap<string, boolean> {
	return useSyncExternalStore(
		subscribe,
		() => folds,
		() => folds,
	);
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

// -- What the popup lists ----------------------------------------------------

/** One group of snippets. `heading` is null when no snippet names a group. */
export type SearchGroup = { heading: string | null; items: Searchable[] };

/** The snippets in their groups, the groups in registry order, the ungrouped last. */
export function searchGroups(searchable: Searchable[]): SearchGroup[] {
	return menuSections("", searchable);
}

/** A box over several kinds: all ticked, none, or some. */
export type Tick = boolean | "indeterminate";

/** How `names` read as one box, given the kinds unticked. Empty reads unticked. */
export function tickOf(names: readonly string[], unticked: ReadonlySet<string>): Tick {
	const on = names.filter((n) => !unticked.has(n)).length;
	if (on === 0) return false;
	return on === names.length ? true : "indeterminate";
}
