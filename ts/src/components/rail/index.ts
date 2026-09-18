// The rail primitive, shared by the pages rail and the apps rail.
//
// One is a nested tree and the other is a flat list, which is the only real
// difference between them. Everything else - the header strip, the row shell,
// the three lanes, the right-click menu, the in-row editor, the roving
// tabindex - is the same furniture on two surfaces, and a user should not have
// to learn it twice.
//
// What stays with each rail is what each rail means: the tree's flatten,
// guides, twisty and expand/collapse arrows; the apps list's status dot,
// restart and rename plumbing. Those are not the same thing at two depths.
//
//   header.tsx        the strip and its add button
//   row.tsx           the tree item, its lanes, its label anchor
//   row-input.tsx     the in-row rename/create editor
//   roving-focus.ts   one tab stop per rail, arrows inside it
//
// Whole directory is a ui-kit graduation candidate.

export { RailHeader } from "./header";
export type { RailFocus } from "./roving-focus";
export { useRailFocus } from "./roving-focus";
export { RailRow, RailRowLink } from "./row";
export { RailRowInput } from "./row-input";
