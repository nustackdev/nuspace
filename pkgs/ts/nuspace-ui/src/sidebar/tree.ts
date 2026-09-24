// The rail's rows: the tree flattened into what the fold state shows.
//
// The tree is flattened into the list of currently visible rows before it is
// rendered. Recursion made every cross-row question (what is below me, who is
// my parent, where does the indent guide run) unanswerable, which is why there
// was no keyboard model at all. Off a flat list it is a `role="tree"` with a
// roving tabindex and the usual four arrows.

import { childrenOf, KIND_GROUP, type PageTree, type RowKind } from "./types";

/** One visible line of the tree, in render order. */
export type VisibleRow = {
	/** Expansion + focus key. A row id, which is unique space-wide. */
	key: string;
	id: string;
	kind: RowKind;
	/** The section this row is in. A section's own group is itself. */
	group: string;
	depth: number;
	title: string;
	hasKids: boolean;
	open: boolean;
	/** Row key of the parent, or null at the top. */
	parent: string | null;
	/** 1-based position among *siblings*, which is what aria-posinset means. */
	pos: number;
	/** Number of siblings, for aria-setsize. */
	size: number;
};

/** Whether a row folds. A section always does, even while it holds nothing. */
export function folds(row: VisibleRow): boolean {
	return row.kind === KIND_GROUP || row.hasKids;
}

/** Walk the tree into the flat list of rows the current fold state shows. */
function flatten(
	tree: PageTree,
	id: string,
	group: string,
	depth: number,
	parent: string | null,
	pos: number,
	size: number,
	expanded: Set<string>,
	out: VisibleRow[],
): void {
	const row = tree[id];
	if (!row) return;
	const kids = childrenOf(tree, id);
	const open = expanded.has(id);
	out.push({
		key: id,
		id,
		kind: row.kind,
		group,
		depth,
		title: row.title || "Untitled",
		hasKids: kids.length > 0,
		open,
		parent,
		pos,
		size,
	});
	if (!open) return;
	kids.forEach((kid, i) => {
		flatten(tree, kid.id, group, depth + 1, id, i + 1, kids.length, expanded, out);
	});
}

/**
 * Every visible row under `sections`, which are the top level: the root is
 * walked through rather than drawn, so each section names the group
 * everything under it belongs to.
 */
export function visibleRows(
	tree: PageTree,
	sections: { id: string }[],
	expanded: Set<string>,
): VisibleRow[] {
	const out: VisibleRow[] = [];
	sections.forEach((section, i) => {
		flatten(tree, section.id, section.id, 0, null, i + 1, sections.length, expanded, out);
	});
	return out;
}

/** A row and everything under it, which is what a delete takes. */
export function subtreeOf(tree: PageTree, id: string): string[] {
	const out = [id];
	for (const kid of childrenOf(tree, id)) out.push(...subtreeOf(tree, kid.id));
	return out;
}
