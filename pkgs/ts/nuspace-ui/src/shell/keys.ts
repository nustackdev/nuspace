// The keyboard shortcuts sheet: whether it is open, the key that opens it, and
// what it lists.
//
// Opened from the rail's bottom bar or with cmd/ctrl+/, from anywhere, so its
// state is a module level store like ./confirm.ts, and the one dialog that
// draws it (./KeysDialog.tsx) is mounted once, at the root.
//
// The list is written by hand, beside the handlers it describes rather than
// read off them: a binding is a few lines in a keydown handler, scattered
// over the features that own them, and most of what a reader needs (where
// the focus has to be, what the key does there) is not in the code at all.
// Change a binding and change its line here.

import { useEffect, useSyncExternalStore } from "react";
import { NEW_INSIDE_KEYS, NEW_PLANE_KEYS } from "../sidebar/add";
import { RAIL_KEYS } from "../sidebar/collapse";
import { DESK_CLICK, DESK_KEYS, OPEN_KEYS } from "../sidebar/keys";
import { SEARCH_KEYS } from "../sidebar/search";

/** The shortcut by key name; the kit `Shortcut` spells it. */
export const KEYS_KEYS = ["mod", "/"] as const;

let open = false;
const subscribers = new Set<() => void>();

function emit(): void {
	for (const cb of subscribers) cb();
}

function subscribe(cb: () => void): () => void {
	subscribers.add(cb);
	return () => subscribers.delete(cb);
}

export function setKeysOpen(next: boolean): void {
	if (open === next) return;
	open = next;
	emit();
}

export function useKeysOpen(): boolean {
	return useSyncExternalStore(
		subscribe,
		() => open,
		() => open,
	);
}

/** Cmd/ctrl+/ flips the sheet from anywhere in the window. Mount it once. */
export function useKeysShortcut(): void {
	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			if (e.key !== "/" || !(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey) return;
			e.preventDefault();
			setKeysOpen(!open);
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, []);
}

/**
 * One line of the sheet: what it does, and its keys. More than one entry in
 * `keys` is "either of these".
 */
export type Binding = { does: string; keys: readonly (readonly string[])[] };

/** A group of lines, under where the focus has to be for them to work. */
export type BindingGroup = { title: string; bindings: Binding[] };

export const BINDINGS: BindingGroup[] = [
	{
		title: "Anywhere",
		bindings: [
			{ does: "Search", keys: [SEARCH_KEYS] },
			{ does: "New plane", keys: [NEW_PLANE_KEYS] },
			{ does: "New plane inside the current one", keys: [NEW_INSIDE_KEYS] },
			{ does: "Show or hide the sidebar", keys: [RAIL_KEYS] },
			{ does: "Keyboard shortcuts", keys: [KEYS_KEYS] },
		],
	},
	{
		title: "Sidebar",
		bindings: [
			{ does: "Move up and down", keys: [["up"], ["down"]] },
			{ does: "Unfold, or step in", keys: [["right"]] },
			{ does: "Fold, or step out", keys: [["left"]] },
			{ does: "Open", keys: [OPEN_KEYS, ["space"]] },
			{ does: "Open on desk", keys: [DESK_KEYS, DESK_CLICK] },
			{ does: "Open in a browser tab", keys: [["mod", "Click"]] },
		],
	},
	{
		title: "Title",
		bindings: [
			{ does: "Done", keys: [["enter"]] },
			{ does: "Undo the edit", keys: [["esc"]] },
			{ does: "Into the first cell", keys: [["down"]] },
		],
	},
	{
		title: "Writing",
		bindings: [
			{ does: "New cell below", keys: [["mod", "enter"]] },
			{ does: "Delete an empty cell", keys: [["backspace"]] },
			{ does: "Insert a snippet, on a new line", keys: [["/"]] },
		],
	},
	{
		title: "Code",
		bindings: [
			{ does: "Save the source", keys: [["mod", "enter"]] },
			{ does: "Save and leave", keys: [["esc"]] },
		],
	},
	{
		title: "Selected cells",
		bindings: [
			{ does: "Copy", keys: [["mod", "C"]] },
			{ does: "Delete", keys: [["backspace"]] },
			{ does: "Clear the selection", keys: [["esc"]] },
		],
	},
];
