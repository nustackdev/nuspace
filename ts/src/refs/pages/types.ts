// PagesRef wire types + coercion.
//
// msgpack payloads arrive untyped, so every field is narrowed here and
// nowhere else. Everything downstream can assume these shapes.
//
// ## The tree is flat
//
// The server keeps every page in one dict keyed by id, and the hierarchy is
// data on the page: `parent`, and an ordered `children`. So `set_tree` ships
// a *list of rows*, not a nested node, and this file rebuilds nothing -- the
// rail walks `children` from the root, which is the one row whose parent is
// itself.
//
// There is no page path. A page is addressed by id at a fixed depth, however
// deep it sits, so the URL is /pages/<page_id> and an op carries an id.
//
// Section order is list position in `section_order` on the server, so blocks
// arrive already in order and carry no `order` field to renormalise.

/** One page, as the server ships it. The root page is its own parent. */
export type PageRow = {
	id: string;
	title: string;
	parent: string;
	children: string[];
};

/** Every page in the space, keyed by id. What the rail walks. */
export type PageTree = Record<string, PageRow>;

/**
 * Provenance, not type. Every block is a Nu program; `tpl` says what made
 * the one it stores. The editor reads it to pick an affordance and for
 * nothing else -- see `nuspace/core/tpl.py` for the registry it mirrors.
 */
export type BlockTpl = "text" | "program";

/** Fixed contract, shared with the out-of-process executor. Do not redesign. */
export type SectionState = "invalid" | "idle" | "starting" | "running" | "stopped" | "failed";

export type SectionStatus = {
	section_id: string;
	state: SectionState;
	error: string | null;
	started_at: number | null;
};

export type Block = {
	id: string;
	name: string;
	tpl: BlockTpl;
	/** The Nu program this block stores. For a `text` block it is the
	 *  template, identical for every text block on the page. */
	source: string;
	/** Never null. Every block compiles, runs and is supervised. */
	status: SectionStatus;
};

// A block carries no field list. The refs its program mounts arrive as
// ordinary nodes under the block's own address and the browser learns them
// from the write stream -- see ./blocks.ts, which is the one file that knows
// where that address is.

export type ActivePage = {
	page_id: string;
	title: string;
	parent: string;
	children: string[];
	blocks: Block[];
};

export type PagesValue = { tree: PageTree; page: ActivePage | null; loaded: boolean };

export const EMPTY_TREE: PageTree = {};

/** `invalid` never compiled; `failed` ran and died. They read differently. */
export function isBad(s: SectionState): boolean {
	return s === "invalid" || s === "failed";
}

export function isLive(s: SectionState): boolean {
	return s === "running" || s === "starting";
}

// -- tree walking ------------------------------------------------------------

/**
 * The space's root page id, or "" when the tree has not landed.
 *
 * Found rather than hardcoded: the root is the one page that parents itself,
 * which is exactly the invariant the store maintains.
 */
export function rootId(tree: PageTree): string {
	for (const id in tree) {
		if (tree[id].parent === id) return id;
	}
	return "";
}

/** A page's children as rows, skipping ids the tree does not hold. */
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
 * Every ancestor of a page, root first, the page itself excluded.
 *
 * Bounded by the number of rows: a cycle in `parent` would otherwise spin
 * here, and the browser is not the place to trust the store's invariants.
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

const STATES: SectionState[] = ["invalid", "idle", "starting", "running", "stopped", "failed"];

export function coerceStatus(raw: unknown): SectionStatus | null {
	if (!raw || typeof raw !== "object") return null;
	const r = raw as Record<string, unknown>;
	const state = String(r.state ?? "idle") as SectionState;
	return {
		section_id: String(r.section_id ?? ""),
		state: STATES.includes(state) ? state : "idle",
		error: r.error ? String(r.error) : null,
		started_at: typeof r.started_at === "number" && r.started_at > 0 ? r.started_at : null,
	};
}

export function coerceBlocks(raw: unknown): Block[] {
	if (!Array.isArray(raw)) return [];
	const out: Block[] = [];
	for (const b of raw) {
		if (!b || typeof b !== "object") continue;
		const r = b as Record<string, unknown>;
		const id = String(r.id ?? "");
		if (!id) continue;
		out.push({
			id,
			name: String(r.name ?? id),
			tpl: r.tpl === "text" ? "text" : "program",
			source: String(r.source ?? ""),
			status: coerceStatus(r.status) ?? {
				section_id: id,
				state: "idle",
				error: null,
				started_at: null,
			},
		});
	}
	return out;
}

// -- id minting --------------------------------------------------------------

let _seq = 0;

/**
 * A time-ordered id, the same shape `nuspace.core.ids.mint_ordered_id` makes.
 *
 * The browser mints page, section and app ids, which is what makes a create a pure
 * function of its event -- re-running the arm rewrites one row instead of
 * adding another -- and what lets a click navigate to the page it just made
 * without waiting to be told its name.
 */
export function mintId(prefix: "p" | "s" | "a"): string {
	const stamp = Date.now().toString(16).padStart(12, "0");
	const seq = (_seq++ % 0x10000).toString(16).padStart(4, "0");
	const tail = Math.floor(Math.random() * 0x10000)
		.toString(16)
		.padStart(4, "0");
	return `${prefix}_${stamp}_${seq}_${tail}`;
}
