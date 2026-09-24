// The rail's rows: the tree flattened into what the fold state shows.
//
// The tree is flattened into the list of currently visible rows before it is
// rendered. Recursion made every cross-row question (what is below me, who is
// my parent, where does the indent guide run) unanswerable, which is why there
// was no keyboard model at all. Off a flat list it is a `role="tree"` with a
// roving tabindex and the usual four arrows.

import { childrenOf, type PlaneTree, type RowKind } from "./types";

/** One visible line of the tree, in render order. */
export type VisibleRow = {
	/** Expansion + focus key. A row id, which is unique space-wide. */
	key: string;
	id: string;
	kind: RowKind;
	depth: number;
	title: string;
	/** The registered Plane it was made from, for its icon. */
	made_by: string;
	hasKids: boolean;
	open: boolean;
	/** Row key of the parent, or null at the top. */
	parent: string | null;
	/** 1-based position among *siblings*, which is what aria-posinset means. */
	pos: number;
	/** Number of siblings, for aria-setsize. */
	size: number;
};

/**
 * Whether an open row shows the "No planes inside" line under it. Every plane
 * folds and unfolds, leaf or not, the way Notion's pages do; a leaf that is
 * open has nothing to show but that line.
 */
export function showsNoPlanes(row: VisibleRow): boolean {
	return row.open && !row.hasKids;
}

/** Walk the tree into the flat list of rows the current fold state shows. */
function flatten(
	tree: PlaneTree,
	id: string,
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
		depth,
		title: row.title || "Untitled",
		made_by: row.made_by,
		hasKids: kids.length > 0,
		open,
		parent,
		pos,
		size,
	});
	if (!open) return;
	kids.forEach((kid, i) => {
		flatten(tree, kid.id, depth + 1, id, i + 1, kids.length, expanded, out);
	});
}

/**
 * Every visible row under `top`, the root's children: the root is walked
 * through rather than drawn, since the header strip stands in for it.
 */
export function visibleRows(
	tree: PlaneTree,
	top: { id: string }[],
	expanded: Set<string>,
): VisibleRow[] {
	const out: VisibleRow[] = [];
	top.forEach((row, i) => {
		flatten(tree, row.id, 0, null, i + 1, top.length, expanded, out);
	});
	return out;
}

/** A row and everything under it, which is what a delete takes. */
export function subtreeOf(tree: PlaneTree, id: string): string[] {
	const out = [id];
	for (const kid of childrenOf(tree, id)) out.push(...subtreeOf(tree, kid.id));
	return out;
}
