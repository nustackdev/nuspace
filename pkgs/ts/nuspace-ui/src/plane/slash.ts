// What the `/` menu lists: the empty program pinned on top, the registered
// Cells under it.
//
// Every cell is a program, so the empty one is not a Cell: it is the
// primitive, and a Cell is the same insert with the source filled in. It
// needs no registry entry, which is why it is here and not in one. It still
// filters with the query like any row, so a query it misses never puts it
// under the caret.

import { type MenuSection, menuScore, menuSections } from "../menu/rank";
import type { CellSpec } from "./types";

/** The empty program. Its name is no Cell's, so the cell stores the server's starter program. */
export const PROGRAM: CellSpec = {
	name: "",
	label: "Empty",
	icon: "square-terminal",
	description: "A cell with a starter program, to write your own.",
};

/** The menu's sections for `query`: the empty program first when it matches. */
export function slashSections(query: string, cellSpecs: CellSpec[]): MenuSection<CellSpec>[] {
	const rest = menuSections(query, cellSpecs);
	return menuScore(query, PROGRAM) === null ? rest : [{ heading: null, items: [PROGRAM] }, ...rest];
}

/** The rows in menu order, flat: what the arrows step through. */
export function slashItems(query: string, cellSpecs: CellSpec[]): CellSpec[] {
	return slashSections(query, cellSpecs).flatMap((s) => s.items);
}
