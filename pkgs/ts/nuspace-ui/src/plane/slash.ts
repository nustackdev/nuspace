// What the `/` menu lists: the empty program pinned on top, the registered
// snippets under it.
//
// Every cell is a program, so the empty one is not a snippet: it is the
// primitive, and a snippet is the same insert with the source filled in. It
// needs no registry entry, which is why it is here and not in one. It still
// filters with the query like any row, so a query it misses never puts it
// under the caret.

import { type MenuSection, menuScore, menuSections } from "../menu/rank";
import type { SlashSnippet } from "./types";

/** The empty program. Its name is no snippet's, so the cell stores the server's starter program. */
export const PROGRAM: SlashSnippet = {
	name: "",
	label: "Empty",
	icon: "square-terminal",
	description: "A cell with a starter program, to write your own.",
};

/** The menu's sections for `query`: the empty program first when it matches. */
export function slashSections(
	query: string,
	snippets: SlashSnippet[],
): MenuSection<SlashSnippet>[] {
	const rest = menuSections(query, snippets);
	return menuScore(query, PROGRAM) === null ? rest : [{ heading: null, items: [PROGRAM] }, ...rest];
}

/** The rows in menu order, flat: what the arrows step through. */
export function slashItems(query: string, snippets: SlashSnippet[]): SlashSnippet[] {
	return slashSections(query, snippets).flatMap((s) => s.items);
}
