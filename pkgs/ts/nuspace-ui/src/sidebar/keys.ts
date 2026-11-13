// A plane row's keys by name, shared by the tree's handler, the plane menu's
// hints and the shortcuts sheet. The kit `Shortcut` spells them.

/** Open the focused row: a plane solo, a desk item as it is now. */
export const OPEN_KEYS = ["enter"] as const;

/** Open a plane to the side: Option Cmd click on its row or any link to it. */
export const SIDE_KEYS = ["alt", "mod", "Click"] as const;
