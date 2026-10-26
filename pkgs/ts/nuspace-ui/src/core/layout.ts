// The desk's layout: which Planes are open as panes, left to right, what
// each one's params are, and which pane has focus. Pure data and pure moves,
// no DOM and no history: ./router.ts binds them to the kit's History.
//
// A layout lives in the History entry's state, `{panes: [{plane, params}],
// focus}`, so back, forward and reload bring it back exactly. The URL names
// one thing, the focused pane: `/<plane>?<its params>` (`/movie?id=42`). An
// entry with no layout in its state (a copied link, a new tab, a URL typed
// in) is one pane, that plane with its query. When the state has one, the
// URL still wins for the pane it names: that pane takes focus and the URL's
// query as its params, so a query rewrite through the kit's HistoryRef
// (`set_query`) lands on the focused pane.
//
// A Plane id is one path segment, URI-encoded. "/" names no Plane and is home
// (the router replaces it with /home), and so is anything deeper than one
// segment. A Plane appears at most once: the server runs one plane per tab,
// so opening one that is already open moves to its pane instead.
//
// Every move is `(layout, ...) -> layout` and never mutates its input. Moves
// on a pane already open take the target's params, the whole set: a link
// says the whole place. A drop is the one exception (`openAt`), since a drag
// carries a Plane and nothing else.

import { type Entry, parseQuery, serializeQuery } from "@nustackdev/ui-kit";

/** The home Plane's id, fixed by the host. */
export const HOME = "home";

/** One pane's params. Strings only: the focused pane's are the URL's query. */
export type Params = Record<string, string>;

/** One pane: its Plane and its params. Also what a link points at. */
export type PaneEntry = { plane: string; params: Params };

/** What the History entry's state holds. `focus` indexes `panes`. */
export type Layout = { panes: PaneEntry[]; focus: number };

/** Where a link or a program asks to go: one Plane with its params. */
export type Target = PaneEntry;

/** Home, as one pane. What an empty desk falls back to. */
export function homeLayout(): Layout {
	return { panes: [{ plane: HOME, params: {} }], focus: 0 };
}

function decode(raw: string): string | null {
	try {
		return decodeURIComponent(raw);
	} catch {
		return null;
	}
}

/** The Plane a pathname names, or null when it names none ("/", deeper paths). */
export function planeOfPath(pathname: string): string | null {
	const parts = pathname.split("/").filter((s) => s.length > 0);
	if (parts.length !== 1) return null;
	return decode(parts[0]) || null;
}

/** A pane's URL: `/<plane>`, with `?<params>` when it has any. */
export function hrefOf(target: Target): string {
	const search = serializeQuery(target.params);
	return `/${encodeURIComponent(target.plane)}${search ? `?${search}` : ""}`;
}

/** The URL a layout lives at: its focused pane's. "/" for an empty one. */
export function urlOf(layout: Layout): string {
	const pane = layout.panes[layout.focus];
	return pane ? hrefOf(pane) : "/";
}

/**
 * Where an href goes, or null when it is not a pane: a hash, or more than one
 * path segment. Bare "/" is home. The href is the app's form, path and query
 * ("/movie?id=42"); an absolute one is read by its path, and the caller
 * checks its origin.
 */
export function targetOfHref(href: string): Target | null {
	let url: URL;
	try {
		url = new URL(href, "http://nuspace.invalid/");
	} catch {
		return null;
	}
	if (url.hash) return null;
	if (url.pathname.split("/").filter(Boolean).length === 0) return { plane: HOME, params: {} };
	const plane = planeOfPath(url.pathname);
	return plane ? { plane, params: parseQuery(url.search) } : null;
}

function paramsOf(raw: unknown): Params {
	const out: Params = {};
	if (!raw || typeof raw !== "object" || Array.isArray(raw)) return out;
	for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
		if (typeof v === "string") out[k] = v;
	}
	return out;
}

/** The layout an entry's state holds, or null when it holds none we can read. */
export function stateLayout(state: unknown): Layout | null {
	if (!state || typeof state !== "object") return null;
	const { panes, focus } = state as { panes?: unknown; focus?: unknown };
	if (!Array.isArray(panes)) return null;
	const out: PaneEntry[] = [];
	for (const raw of panes) {
		const plane = (raw as { plane?: unknown } | null)?.plane;
		if (typeof plane !== "string" || !plane || out.some((p) => p.plane === plane)) continue;
		out.push({ plane, params: paramsOf((raw as { params?: unknown }).params) });
	}
	if (!out.length) return null;
	const at = typeof focus === "number" && Number.isInteger(focus) ? focus : 0;
	return { panes: out, focus: Math.min(Math.max(at, 0), out.length - 1) };
}

/**
 * The layout an entry is: its state's, with the pane its URL names focused and
 * on the URL's query; one pane off the URL when the state has none or does not
 * hold that Plane; home when the URL names no Plane.
 */
export function layoutOf(entry: Pick<Entry, "path" | "query" | "state">): Layout {
	const plane = planeOfPath(entry.path);
	if (!plane) return homeLayout();
	const params = { ...entry.query };
	const held = stateLayout(entry.state);
	const at = held ? held.panes.findIndex((p) => p.plane === plane) : -1;
	if (!held || at < 0) return { panes: [{ plane, params }], focus: 0 };
	return { panes: held.panes.map((p, i) => (i === at ? { plane, params } : p)), focus: at };
}

/** The Planes open, left to right. */
export function planesOf(layout: Layout): string[] {
	return layout.panes.map((p) => p.plane);
}

/** The pane showing `plane`, or -1. */
export function indexOf(layout: Layout, plane: string): number {
	return layout.panes.findIndex((p) => p.plane === plane);
}

function clampSlot(index: number, length: number): number {
	return index >= 0 && index < length ? index : length;
}

function copy(target: Target): PaneEntry {
	return { plane: target.plane, params: { ...target.params } };
}

/** `target`'s pane, already open at `at`, with its params and focus. */
function retarget(layout: Layout, at: number, target: Target): Layout {
	return { panes: layout.panes.map((p, i) => (i === at ? copy(target) : p)), focus: at };
}

/** A link followed: `target` in the focused pane. Already open: that pane, refocused. */
export function openHere(layout: Layout, target: Target): Layout {
	const at = indexOf(layout, target.plane);
	if (at >= 0) return retarget(layout, at, target);
	if (!layout.panes.length) return { panes: [copy(target)], focus: 0 };
	return retarget(layout, layout.focus, target);
}

/** Option on a link: `target` in a new pane right after the focused one, focused. */
export function openBeside(layout: Layout, target: Target): Layout {
	const at = indexOf(layout, target.plane);
	if (at >= 0) return retarget(layout, at, target);
	const slot = layout.panes.length ? layout.focus + 1 : 0;
	const panes = [...layout.panes];
	panes.splice(slot, 0, copy(target));
	return { panes, focus: slot };
}

/**
 * A Plane dropped on the desk: a new pane at `index` (the end when out of
 * range), focused. Already open: that pane takes focus and keeps its params.
 */
export function openAt(layout: Layout, target: Target, index: number): Layout {
	const at = indexOf(layout, target.plane);
	if (at >= 0) return focus(layout, at);
	const panes = [...layout.panes];
	const slot = clampSlot(index, panes.length);
	panes.splice(slot, 0, copy(target));
	return { panes, focus: slot };
}

/**
 * The panes showing any of `planes` closed. A focused one closing hands focus
 * to its neighbour on the left, or the new leftmost. The last one closing is
 * home.
 */
export function close(layout: Layout, planes: string[]): Layout {
	const gone = new Set(planes);
	const panes = layout.panes.filter((p) => !gone.has(p.plane));
	if (panes.length === layout.panes.length) return layout;
	if (!panes.length) return homeLayout();
	const focused = layout.panes[layout.focus]?.plane ?? "";
	if (!gone.has(focused))
		return { panes, focus: Math.max(indexOf({ panes, focus: 0 }, focused), 0) };
	const first = layout.panes.findIndex((p) => gone.has(p.plane));
	const left = layout.panes
		.slice(0, first)
		.reverse()
		.find((p) => !gone.has(p.plane));
	return { panes, focus: left ? panes.indexOf(left) : 0 };
}

/** The pane showing `plane` moved to `index` among the others (counted without it), focused. */
export function move(layout: Layout, plane: string, index: number): Layout {
	const at = indexOf(layout, plane);
	if (at < 0) return layout;
	const pane = layout.panes[at];
	const panes = layout.panes.filter((_, i) => i !== at);
	const slot = clampSlot(index, panes.length);
	panes.splice(slot, 0, pane);
	return { panes, focus: slot };
}

/** Pane `index` focused. Out of range: unchanged. */
export function focus(layout: Layout, index: number): Layout {
	if (index < 0 || index >= layout.panes.length || index === layout.focus) return layout;
	return { panes: layout.panes, focus: index };
}
