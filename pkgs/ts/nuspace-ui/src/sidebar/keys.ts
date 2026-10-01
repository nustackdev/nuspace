// A plane row's keys by name, shared by the tree's handler, the plane menu's
// hints and the shortcuts sheet. The kit `Shortcut` spells them.

/** Open the focused row's plane in the focused pane. */
export const OPEN_KEYS = ["enter"] as const;

/** Open it beside the others, in a new pane. */
export const SPLIT_KEYS = ["alt", "enter"] as const;

/** The same, with the pointer. */
export const SPLIT_CLICK = ["alt", "Click"] as const;
