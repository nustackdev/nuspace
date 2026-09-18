// SidebarRef wire types + coercion.
//
// msgpack payloads arrive untyped, so every field is narrowed here and nowhere
// else. Everything downstream can assume these shapes.
//
// ## The tree is flat
//
// The server keeps every Plane in one dict keyed by id, and the hierarchy is
// data on the row: `parent`, and an ordered `children`. So `set_tree` ships a
// *list of rows*, not a nested node, and this file rebuilds nothing -- the
// sidebar walks `children` from the root, which is the one row whose parent is
// itself.
//
// There is no path to a Plane. It is addressed by id at a fixed depth however
// it is grouped, so the URL is /<plane id> and an op carries an id.

/** One Plane, as the server ships it. The root row is its own parent. */
export type PageRow = {
	id: string;
	title: string;
	parent: string;
	children: string[];
};

/** Every Plane that draws, keyed by id. What the sidebar walks. */
export type PageTree = Record<string, PageRow>;

export type SidebarValue = { tree: PageTree; loaded: boolean };

export const EMPTY_TREE: PageTree = {};

// -- tree walking ------------------------------------------------------------

/**
 * The root row's id, or "" when the tree has not landed.
 *
 * Found rather than hardcoded: the root is the one row that parents itself,
 * which is exactly the invariant the server maintains.
 */
export function rootId(tree: PageTree): string {
	for (const id in tree) {
		if (tree[id].parent === id) return id;
	}
	return "";
}

/** A row's children as rows, skipping ids the tree does not hold. */
export function childrenOf(tree: PageTree, id: string): PageRow[] {
	const row = tree[id];
	if (!row) return [];
	const out: PageRow[] = [];
	for (const kid of row.children) {
		const r = tree[kid];
		if (r) out.push(r);
	}
	return out;
}

/**
 * Every ancestor of a row, root first, the row itself excluded.
 *
 * Bounded by the number of rows: a cycle in `parent` would otherwise spin here,
 * and the browser is not the place to trust the server's invariants.
 */
export function ancestorsOf(tree: PageTree, id: string): PageRow[] {
	const out: PageRow[] = [];
	const seen = new Set<string>([id]);
	let at = tree[id]?.parent ?? "";
	while (at && tree[at] && !seen.has(at)) {
		seen.add(at);
		out.push(tree[at]);
		at = tree[at].parent;
	}
	return out.reverse();
}

// -- coercion ----------------------------------------------------------------

export function coerceStrs(raw: unknown): string[] {
	return Array.isArray(raw) ? raw.map((s) => String(s)) : [];
}

export function coerceTree(raw: unknown): PageTree {
	if (!Array.isArray(raw)) return {};
	const out: PageTree = {};
	for (const p of raw) {
		if (!p || typeof p !== "object") continue;
		const r = p as Record<string, unknown>;
		const id = String(r.id ?? "");
		if (!id) continue;
		out[id] = {
			id,
			title: String(r.title ?? ""),
			parent: String(r.parent ?? id),
			children: coerceStrs(r.children),
		};
	}
	return out;
}
