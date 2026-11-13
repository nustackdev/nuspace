// The keyboard shortcuts sheet: what it lists. Whether it is open, and the
// key that opens it, are ../core/keys.ts.
//
// The list is written by hand, next to the handlers it describes rather than
// read off them: a binding is a few lines in a keydown handler, scattered
// over the features that own them, and most of what a reader needs (where
// the focus has to be, what the key does there) is not in the code at all.
// Change a binding and change its line here.

import { KEYS_KEYS } from "../core/keys";
import {
	HOME_KEYS,
	NEW_INSIDE_KEYS,
	NEW_PLANE_KEYS,
	OPEN_KEYS,
	SEARCH_KEYS,
	SETTINGS_KEYS,
	SIDE_KEYS,
	SIDEBAR_KEYS,
} from "../sidebar/api";

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
			{ does: "Home", keys: [HOME_KEYS] },
			{ does: "Search", keys: [SEARCH_KEYS] },
			{ does: "Settings", keys: [SETTINGS_KEYS] },
			{ does: "New plane", keys: [NEW_PLANE_KEYS] },
			{ does: "New plane inside the current one", keys: [NEW_INSIDE_KEYS] },
			{ does: "Show or hide the sidebar", keys: [SIDEBAR_KEYS] },
			{ does: "Keyboard shortcuts", keys: [KEYS_KEYS] },
			{ does: "Open a link to the side", keys: [SIDE_KEYS] },
		],
	},
	{
		title: "Sidebar",
		bindings: [
			{ does: "Move up and down", keys: [["up"], ["down"]] },
			{ does: "Unfold, or step in", keys: [["right"]] },
			{ does: "Fold, or step out", keys: [["left"]] },
			{ does: "Open", keys: [OPEN_KEYS, ["space"]] },
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
			{ does: "Insert a cell, on a new line", keys: [["/"]] },
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
