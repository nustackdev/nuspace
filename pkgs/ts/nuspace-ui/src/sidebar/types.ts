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
// deep it is nested, so the URL is /<plane id> and an op carries an id.
//
// ## Two kinds of row
//
// A row says what it is in `kind`. `plane` is a Plane in the store; `space` is
// the one row the server invents so the tree has a root, with the id
// `ROOT_ID`, parenting itself. There is no grouping row: grouping is nesting,
// and a Plane with no cells works as a folder.
//
// An unknown `kind` is dropped rather than bucketed. A row whose parent this
// build has no row for is simply not in the tree.
//
// ## Pins
//
// `set_tree` also ships `pinned`, the ids pinned to the row under the top bar,
// in order. A pin is a shortcut: the Plane is in the tree as well.

/** What a row is. The Space, or a Plane. */
export const KIND_SPACE = "space";
export const KIND_PLANE = "plane";

export type RowKind = typeof KIND_SPACE | typeof KIND_PLANE;

const KINDS: readonly string[] = [KIND_SPACE, KIND_PLANE];

/** The Space row's id, and the `parent_id` that means "at the top". */
export const ROOT_ID = "space";

/** One row, as the server ships it. The root row is its own parent. */
export type TreeRow = {
	id: string;
	kind: RowKind;
	title: string;
	parent: string;
	/** Already in sibling order. */
	children: string[];
	/** The registered Plane it was created from, "" when none. Its icon is the fallback. */
	made_by: string;
	/** The plane's own `meta.icon`, "" when it has none. See ../icon/parse.ts. */
	icon: string;
	/** A protected Plane (home, settings, a service): the server refuses its delete. */
	system: boolean;
};

/** One registered Plane, as the Add plane popup offers it. Seeded at boot. */
export type Registered = {
	name: string;
	label: string;
	/** A lucide icon name, "" for the default. Any spelling ../icon/parse.ts reads. */
	icon: string;
	description: string;
};

/** Every Plane that draws, keyed by id. What the sidebar walks. */
export type PlaneTree = Record<string, TreeRow>;

export type SidebarValue = {
	tree: PlaneTree;
	/** The pinned Plane ids, in order. Every one is in `tree` too. */
	pinned: string[];
	loaded: boolean;
	registered: Registered[];
};

export const EMPTY_TREE: PlaneTree = {};

// -- Tree walking ------------------------------------------------------------

/**
 * The root row's id, or "" when the tree has not landed.
 *
 * Found rather than hardcoded: the root is the one row that parents itself,
 * which is exactly the invariant the server maintains.
 */
export function rootId(tree: PlaneTree): string {
	for (const id in tree) {
		if (tree[id].parent === id) return id;
	}
	return "";
}

/** A row's children as rows, skipping ids the tree does not hold. */
export function childrenOf(tree: PlaneTree, id: string): TreeRow[] {
	const row = tree[id];
	if (!row) return [];
	const out: TreeRow[] = [];
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
export function ancestorsOf(tree: PlaneTree, id: string): TreeRow[] {
	const out: TreeRow[] = [];
	const seen = new Set<string>([id]);
	let at = tree[id]?.parent ?? "";
	while (at && tree[at] && !seen.has(at)) {
		seen.add(at);
		out.push(tree[at]);
		at = tree[at].parent;
	}
	return out.reverse();
}

// -- Coercion ----------------------------------------------------------------

export function coerceStrs(raw: unknown): string[] {
	return Array.isArray(raw) ? raw.map((s) => String(s)) : [];
}

export function coerceTree(raw: unknown): PlaneTree {
	if (!Array.isArray(raw)) return {};
	const out: PlaneTree = {};
	for (const p of raw) {
		if (!p || typeof p !== "object") continue;
		const r = p as Record<string, unknown>;
		const id = String(r.id ?? "");
		if (!id) continue;
		// A row whose kind this build does not know is dropped: there is no
		// rule for what it looks like.
		const kind = String(r.kind ?? KIND_PLANE);
		if (!KINDS.includes(kind)) continue;
		out[id] = {
			id,
			kind: kind as RowKind,
			title: String(r.title ?? ""),
			parent: String(r.parent ?? id),
			children: coerceStrs(r.children),
			made_by: String(r.made_by ?? ""),
			icon: typeof r.icon === "string" ? r.icon : "",
			system: r.system === true,
		};
	}
	return out;
}

export function coerceRegistered(raw: unknown): Registered[] {
	if (!Array.isArray(raw)) return [];
	const out: Registered[] = [];
	for (const e of raw) {
		if (!e || typeof e !== "object") continue;
		const r = e as Record<string, unknown>;
		const name = String(r.name ?? "");
		if (!name) continue;
		out.push({
			name,
			label: String(r.label ?? name),
			icon: String(r.icon ?? ""),
			description: String(r.description ?? ""),
		});
	}
	return out;
}
