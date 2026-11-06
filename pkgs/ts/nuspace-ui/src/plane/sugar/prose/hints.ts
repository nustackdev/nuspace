// The prose set's hints, one source for each string.
//
// A hint says what a gesture does on the line where it applies, and nowhere
// else. The input line's is its placeholder (../../input/Ghost.tsx). A prose
// cell's are drawn by its own editor (the kit's `MarkdownHandle.hint`), only
// while the caret is in it: on a blank one, where typing writes and `/`
// stands the menu in for it (R6), and on the empty last line Enter leaves
// you on, where Cmd+Enter opens a line below (R7). Nothing here reaches into
// the editor to draw them.

import { formatShortcut } from "@nustackdev/ui-kit";

/** The input line with a prose default installed, and a blank prose cell. */
export const WRITE_HINT = "Write, or press / for cells";

/** The empty last line of a prose cell with text: R7, the way out below. */
export const NEW_CELL_HINT = `${formatShortcut(["mod", "enter"])} new cell below`;
