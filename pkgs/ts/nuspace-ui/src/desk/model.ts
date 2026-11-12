// The desk model: pure moves over desks. No React, no DOM, no history.
//
// A desk is a saved collection (the task's iteration-3.md), the dict stored
// whole at `Web.desks[id]` and mirrored 1:1 by `Desk` below: a name and its
// items in the user's order. An item is a plane item (one plane, shown alone)
// or a strip (one row of columns, panes top to bottom in each column). A
// column may have a width, px, set by its resize handle; with none it is
// drawn at the default width (../main/Column.tsx). A pane has a share (its
// part of the column's height, the shares in a column sum to 1).
//
// Every plane item and every pane holds `original`, the link it was saved
// with, and maybe `recent`, the link it was last navigated to. What shows is
// `recent ?? original`. Navigation writes `recent` (dropped when it lands
// back on the original), reset drops it, save makes it the original. Both
// per plane item or pane.
//
// Invariants every move keeps (`tidy`): no recent equal to its original, a
// strip never shows the same plane twice, no empty column, shares sum to 1,
// no bad width. The only automatic changes: a strip left with one pane
// becomes a plane item in its place (same id, that pane's original and
// recent), an empty strip goes away. An empty desk stays.
//
// A pane is named by the plane it shows: a strip shows each plane once, and
// that is how the canvas and `Conn.Tab.panes` key it. Focus is per tab and
// never part of a desk; the moves that pick a pane to focus say so
// (`Landed`).
//
// Every move is `(desk, ...) -> desk` and never mutates its input. A move
// that does not apply, or changes nothing, returns its input (same object).
//
// The contract with the server: the web device's `desk_problem`
// (nuspace/web/desks/model.py) is the authority on the shape, and
// every desk a move returns passes it. Reading (`readDesk`) is lenient on top
// of that: it fixes what it can (shares, a duplicate pane, a strip of one
// pane) and refuses the rest.

/** A link's params, strings only (`Conn.Tab.panes[plane].params`). */
export type Params = Record<string, string>;

/** A plane and its params. */
export type Link = { plane: string; params: Params };

/** What a plane item and a pane both hold. */
export type Links = { original: Link; recent?: Link };

export type PlaneItem = { id: string; kind: "plane"; original: Link; recent?: Link };
export type Pane = { share: number; original: Link; recent?: Link };
export type Column = { width?: number; panes: Pane[] };
export type Strip = { id: string; kind: "strip"; columns: Column[] };
export type Item = PlaneItem | Strip;
export type Desk = { name: string; items: Item[] };

/** Where a pane sits in its strip, by index. */
export type Spot = { column: number; pane: number };

/** A pane's drop target: its left or right edge (new column) or its top or bottom half (stack). */
export type Edge = "left" | "right" | "top" | "bottom";

/**
 * Where a pane lands inside a strip:
 *
 * - `{ plane, edge }`: relative to the pane showing `plane`. left / right is a
 *   new column on that side, top / bottom stacks above / below it
 * - `{ at }`: a new column inserted at column index `at`. `at` at or past the
 *   number of columns is the end (the end drop zone)
 * - `{ column }`: stacked at the bottom of column `column` (a column group)
 *
 * Indices are the strip's as drawn, before the move.
 */
export type Drop = { plane: string; edge: Edge } | { at: number } | { column: number };

export type Side = "left" | "right";

/** The narrowest a column gets by its resize handle, and is drawn at, px. */
export const MIN_WIDTH = 400;

/** A new desk's name. */
export const NEW_DESK_NAME = "Untitled";

/** A move's desk and the plane the tab should focus in the item ("" for no change). */
export type Landed = { desk: Desk; focus: string };

// -- Links -------------------------------------------------------------------

/** What a plane item or a pane shows: its recent, else its original. */
export function shown(x: Links): Link {
	return x.recent ?? x.original;
}

/** Whether two links name the same plane with the same params. */
export function sameLink(a: Link, b: Link): boolean {
	if (a.plane !== b.plane) return false;
	const ka = Object.keys(a.params);
	return ka.length === Object.keys(b.params).length && ka.every((k) => a.params[k] === b.params[k]);
}

function copyLink(link: Link): Link {
	return { plane: link.plane, params: { ...link.params } };
}

/** A copy of `x`'s links, a recent equal to the original dropped. */
function linksOf(x: Links): Links {
	const out: Links = { original: copyLink(x.original) };
	if (x.recent && !sameLink(x.recent, x.original)) out.recent = copyLink(x.recent);
	return out;
}

function planeItem(id: string, x: Links): PlaneItem {
	return { id, kind: "plane", ...linksOf(x) };
}

function newPane(share: number, x: Links): Pane {
	return { share, ...linksOf(x) };
}

// -- Reading -----------------------------------------------------------------

/** The item `id` of `desk`, or null. */
export function itemOf(desk: Desk, id: string): Item | null {
	return desk.items.find((i) => i.id === id) ?? null;
}

/** The strip `id` of `desk`, or null when it is no strip. */
export function stripOf(desk: Desk, id: string): Strip | null {
	const item = itemOf(desk, id);
	return item?.kind === "strip" ? item : null;
}

/** Every pane of a strip, columns left to right, panes top to bottom. */
export function panesOf(strip: Strip): Pane[] {
	return strip.columns.flatMap((c) => c.panes);
}

/** Where the pane showing `plane` sits in `strip`, or null. */
export function locate(strip: Strip, plane: string): Spot | null {
	if (!plane) return null;
	for (let c = 0; c < strip.columns.length; c++) {
		const p = strip.columns[c].panes.findIndex((x) => shown(x).plane === plane);
		if (p >= 0) return { column: c, pane: p };
	}
	return null;
}

/** The pane of `strip` showing `plane`, or null. */
export function paneOf(strip: Strip, plane: string): Pane | null {
	const at = locate(strip, plane);
	return at ? strip.columns[at.column].panes[at.pane] : null;
}

/** What an item shows: one link for a plane item, each pane's for a strip, in order. */
export function shownLinks(item: Item): Link[] {
	return item.kind === "plane" ? [shown(item)] : panesOf(item).map(shown);
}

// -- Ids ---------------------------------------------------------------------

const DESK_ID = /^[a-z0-9]{8}$/;
const ITEM_ID = /^[a-z0-9]{6}$/;
const ID_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789";

function mint(length: number, taken: (id: string) => boolean, random: () => number): string {
	for (;;) {
		let id = "";
		for (let i = 0; i < length; i++) id += ID_CHARS[Math.floor(random() * ID_CHARS.length)];
		if (!taken(id)) return id;
	}
}

/** Whether `s` has a desk id's shape: 8 chars `[a-z0-9]`. */
export function isDeskId(s: string): boolean {
	return DESK_ID.test(s);
}

/** Whether `s` has an item id's shape: 6 chars `[a-z0-9]`. */
export function isItemId(s: string): boolean {
	return ITEM_ID.test(s);
}

/** A new desk id that `taken` does not hold. */
export function mintDeskId(taken: (id: string) => boolean, random: () => number = Math.random) {
	return mint(8, taken, random);
}

/** A new item id, unique within `desk`. */
export function mintItemId(desk: Desk, random: () => number = Math.random): string {
	return mint(6, (id) => !!itemOf(desk, id), random);
}

// -- Reading the store -------------------------------------------------------

function isDict(raw: unknown): raw is Record<string, unknown> {
	return !!raw && typeof raw === "object" && !Array.isArray(raw);
}

function readParams(raw: unknown): Params {
	const out: Params = {};
	if (!isDict(raw)) return out;
	for (const [k, v] of Object.entries(raw)) if (typeof v === "string") out[k] = v;
	return out;
}

function num(v: unknown): number {
	return typeof v === "number" ? v : Number.NaN;
}

function readLink(raw: unknown): Link | null {
	if (!isDict(raw) || typeof raw.plane !== "string" || !raw.plane) return null;
	return { plane: raw.plane, params: readParams(raw.params) };
}

function readLinks(raw: Record<string, unknown>): Links | null {
	const original = readLink(raw.original);
	if (!original) return null;
	if (raw.recent === undefined || raw.recent === null) return { original };
	const recent = readLink(raw.recent);
	return recent ? { original, recent } : null;
}

function readItem(raw: unknown): Item | null {
	if (!isDict(raw) || typeof raw.id !== "string" || !isItemId(raw.id)) return null;
	if (raw.kind === "plane") {
		const links = readLinks(raw);
		return links ? { id: raw.id, kind: "plane", ...links } : null;
	}
	if (raw.kind !== "strip" || !Array.isArray(raw.columns)) return null;
	const columns: Column[] = [];
	for (const c of raw.columns) {
		if (!isDict(c) || !Array.isArray(c.panes)) return null;
		const list: Pane[] = [];
		for (const p of c.panes) {
			const links = isDict(p) ? readLinks(p) : null;
			if (!links || !isDict(p)) return null;
			list.push({ share: num(p.share), ...links });
		}
		columns.push(withWidth({ panes: list }, num(c.width)));
	}
	return { id: raw.id, kind: "strip", columns };
}

/**
 * A desk off the store, made whole (`tidy`), or null when it is not a desk
 * dict of this shape: not a dict, an older shape (`strips` or top level
 * `columns`), no string name, no item list, an item without a good id (or one seen before),
 * an unknown kind, a link without a plane. Bad widths are dropped and bad
 * shares fixed, not refused.
 */
export function readDesk(raw: unknown): Desk | null {
	if (!isDict(raw) || "strips" in raw || "columns" in raw || !Array.isArray(raw.items)) return null;
	const items: Item[] = [];
	const ids = new Set<string>();
	for (const r of raw.items) {
		const item = readItem(r);
		if (!item || ids.has(item.id)) return null;
		ids.add(item.id);
		items.push(item);
	}
	if (typeof raw.name !== "string") return null;
	return tidy({ name: raw.name, items });
}

// -- Keeping a desk whole ----------------------------------------------------

/** `column` with `width` when it is a good one (a positive number of px), else with none. */
function withWidth(column: Column, width: number | undefined): Column {
	const out: Column = { panes: column.panes };
	if (width !== undefined && Number.isFinite(width) && width > 0) out.width = width;
	return out;
}

function renorm(list: Pane[]): Pane[] {
	const ok = list.every((p) => Number.isFinite(p.share) && p.share > 0);
	const sum = ok ? list.reduce((a, p) => a + p.share, 0) : 0;
	return list.map((p) => newPane(sum > 0 ? p.share / sum : 1 / list.length, p));
}

/**
 * A desk made whole: recents equal to their original dropped; in a strip a
 * second pane showing a plane dropped, empty columns removed, shares summed
 * to 1, bad widths dropped; a strip of one pane made a plane item in its place,
 * an empty strip removed. Always a fresh copy.
 */
export function tidy(desk: Desk): Desk {
	const items: Item[] = [];
	for (const item of desk.items) {
		if (item.kind === "plane") {
			items.push(planeItem(item.id, item));
			continue;
		}
		const seen = new Set<string>();
		const columns = item.columns
			.map((c) => ({
				...c,
				panes: c.panes.filter((p) => {
					const plane = shown(p).plane;
					if (seen.has(plane)) return false;
					seen.add(plane);
					return true;
				}),
			}))
			.filter((c) => c.panes.length > 0)
			.map((c) => withWidth({ panes: renorm(c.panes) }, c.width));
		const all = columns.flatMap((c) => c.panes);
		if (all.length === 1) items.push(planeItem(item.id, all[0]));
		else if (all.length > 1) items.push({ id: item.id, kind: "strip", columns });
	}
	return { name: desk.name, items };
}

/** A deep copy to mutate. */
function draft(desk: Desk): Desk {
	return JSON.parse(JSON.stringify(desk)) as Desk;
}

function equal(a: unknown, b: unknown): boolean {
	if (a === b) return true;
	if (!a || !b || typeof a !== "object" || typeof b !== "object") return false;
	if (Array.isArray(a) !== Array.isArray(b)) return false;
	const ka = Object.keys(a);
	const rb = b as Record<string, unknown>;
	if (ka.length !== Object.keys(rb).length) return false;
	return ka.every((k) => equal((a as Record<string, unknown>)[k], rb[k]));
}

/** The draft made whole, or `desk` itself when nothing changed. */
function done(desk: Desk, d: Desk): Desk {
	const next = widen(desk, tidy(d));
	return equal(next, desk) ? desk : next;
}

/**
 * A strip that grew past one column drops every width: its one column was
 * drawn full width, whatever it stored, and so lands beside the new one at
 * the same default width.
 */
function widen(was: Desk, next: Desk): Desk {
	for (const item of next.items) {
		if (item.kind !== "strip" || item.columns.length < 2) continue;
		const before = was.items.find((i) => i.id === item.id);
		if (before?.kind === "strip" && before.columns.length > 1) continue;
		for (const c of item.columns) delete c.width;
	}
	return next;
}

function clampIndex(index: number, length: number): number {
	if (Number.isNaN(index)) return length;
	return Math.max(0, Math.min(Math.floor(index), length));
}

// -- Items -------------------------------------------------------------------

/** `item` inserted at `index` (clamped, past the end is the end). Its id taken: unchanged. */
export function addItem(desk: Desk, item: Item, index: number): Desk {
	if (itemOf(desk, item.id)) return desk;
	const d = draft(desk);
	d.items.splice(clampIndex(index, d.items.length), 0, draft({ name: "", items: [item] }).items[0]);
	return done(desk, d);
}

/** `item` put at `index`, with a fresh id when `desk` holds its id already. */
export function putItem(
	desk: Desk,
	item: Item,
	index: number,
	random: () => number = Math.random,
): Desk {
	const id = itemOf(desk, item.id) ? mintItemId(desk, random) : item.id;
	return addItem(desk, { ...item, id }, index);
}

/** The item `id` taken out of `desk`, or null when it is not there. */
export function takeItem(desk: Desk, id: string): { item: Item; desk: Desk } | null {
	const item = itemOf(desk, id);
	return item ? { item, desk: closeItem(desk, id) } : null;
}

/**
 * The item `id` moved to `index`, an index between items as drawn before the
 * move (0 is the top, the item count is the end).
 */
export function moveItem(desk: Desk, id: string, index: number): Desk {
	const from = desk.items.findIndex((i) => i.id === id);
	if (from < 0) return desk;
	let to = clampIndex(index, desk.items.length);
	if (to > from) to -= 1;
	if (to === from) return desk;
	const d = draft(desk);
	const [item] = d.items.splice(from, 1);
	d.items.splice(to, 0, item);
	return done(desk, d);
}

/** The item `id` closed. */
export function closeItem(desk: Desk, id: string): Desk {
	if (!itemOf(desk, id)) return desk;
	return done(desk, { name: desk.name, items: desk.items.filter((i) => i.id !== id) });
}

/** The desk renamed. */
export function rename(desk: Desk, name: string): Desk {
	return name === desk.name ? desk : { ...desk, name };
}

// -- Strips ------------------------------------------------------------------

/** The strip `id` of a draft, or null. */
function draftStrip(d: Desk, id: string): Strip | null {
	return stripOf(d, id);
}

/** A one pane column. */
function soloColumn(x: Links, width?: number): Column {
	return withWidth({ panes: [newPane(1, x)] }, width);
}

/**
 * Put a pane showing `x` into a strip draft at `drop`. False when the drop
 * target is not in the strip. `width` is the width a new column gets, none
 * for the default.
 */
function place(s: Strip, x: Links, drop: Drop, width?: number): boolean {
	if ("at" in drop) {
		if (!(drop.at >= 0)) return false;
		s.columns.splice(Math.min(drop.at, s.columns.length), 0, soloColumn(x, width));
		return true;
	}
	if ("column" in drop) {
		const col = s.columns[drop.column];
		if (!col) return false;
		// Stacked at the bottom: the pane gets 1/(n+1), the others shrink to fit.
		const n = col.panes.length;
		for (const p of col.panes) p.share = (p.share * n) / (n + 1);
		col.panes.push(newPane(n ? 1 / (n + 1) : 1, x));
		return true;
	}
	const at = locate(s, drop.plane);
	if (!at) return false;
	if (drop.edge === "left" || drop.edge === "right") {
		s.columns.splice(at.column + (drop.edge === "right" ? 1 : 0), 0, soloColumn(x, width));
		return true;
	}
	// A half: the target pane gives up half its share to the new one.
	const col = s.columns[at.column];
	const half = col.panes[at.pane].share / 2;
	col.panes[at.pane].share = half;
	col.panes.splice(at.pane + (drop.edge === "bottom" ? 1 : 0), 0, newPane(half, x));
	return true;
}

/**
 * The plane item `id` and `x` (a dropped link, item or pane) made a strip in
 * its place, same id: `x` in a new column on `side`. Unchanged when `id` is
 * no plane item or `x` shows the plane it shows.
 */
export function makeStrip(desk: Desk, id: string, x: Links, side: Side): Desk {
	const at = desk.items.findIndex((i) => i.id === id);
	const target = desk.items[at];
	if (target?.kind !== "plane" || shown(target).plane === shown(x).plane) return desk;
	const own = soloColumn(target);
	const add = soloColumn(x);
	const d = draft(desk);
	d.items[at] = { id, kind: "strip", columns: side === "left" ? [add, own] : [own, add] };
	return done(desk, d);
}

/**
 * A pane showing `x` added to the strip `id` at `drop`. `width` is the width
 * a new column gets, none for the default. Unchanged when `id` is no strip, the drop target is not
 * in it, or the strip shows `x`'s plane already.
 */
export function addPane(desk: Desk, id: string, x: Links, drop: Drop, width?: number): Desk {
	const strip = stripOf(desk, id);
	if (!strip || locate(strip, shown(x).plane)) return desk;
	const d = draft(desk);
	if (!place(draftStrip(d, id) as Strip, x, drop, width)) return desk;
	return done(desk, d);
}

/**
 * The pane showing `plane` moved to `drop` in its own strip `id`, with its
 * links and, when it was alone in its column, its column's width. A drop
 * onto the pane itself, or one that changes nothing, returns `desk`.
 */
export function movePane(desk: Desk, id: string, plane: string, drop: Drop): Desk {
	const strip = stripOf(desk, id);
	const from = strip && locate(strip, plane);
	if (!from || ("plane" in drop && drop.plane === plane)) return desk;
	const d = draft(desk);
	const s = draftStrip(d, id) as Strip;
	const col = s.columns[from.column];
	const width = col.panes.length === 1 ? col.width : undefined;
	const [pane] = col.panes.splice(from.pane, 1);
	if (!place(s, pane, drop, width)) return desk;
	return done(desk, d);
}

/** A pane lifted out of its strip: its links, its column's width when it was alone, the desk without it. */
export type Lifted = { pane: Links; width?: number; desk: Desk };

/**
 * The pane showing `plane` taken out of the strip `id`, or null. The strip
 * rules apply to what is left (one pane: a plane item in its place).
 */
export function takePane(desk: Desk, id: string, plane: string): Lifted | null {
	const strip = stripOf(desk, id);
	const from = strip && locate(strip, plane);
	if (!from) return null;
	const d = draft(desk);
	const col = (draftStrip(d, id) as Strip).columns[from.column];
	const width = col.panes.length === 1 ? col.width : undefined;
	const [pane] = col.panes.splice(from.pane, 1);
	return { pane: linksOf(pane), width, desk: tidy(d) };
}

/** The pane showing `plane` closed. */
export function closePane(desk: Desk, id: string, plane: string): Desk {
	return takePane(desk, id, plane)?.desk ?? desk;
}

/** The column at index `column` of the strip `id` closed, with every pane in it. */
export function closeColumn(desk: Desk, id: string, column: number): Desk {
	const strip = stripOf(desk, id);
	if (!strip?.columns[column]) return desk;
	const d = draft(desk);
	(draftStrip(d, id) as Strip).columns.splice(column, 1);
	return done(desk, d);
}

/** The width, px, of the column of strip `id` holding `plane` set, at least `MIN_WIDTH`. */
export function setWidth(desk: Desk, id: string, plane: string, width: number): Desk {
	const strip = stripOf(desk, id);
	const at = strip && locate(strip, plane);
	if (!at || !Number.isFinite(width)) return desk;
	const d = draft(desk);
	(draftStrip(d, id) as Strip).columns[at.column].width = Math.max(Math.round(width), MIN_WIDTH);
	return done(desk, d);
}

/**
 * The shares of the column of strip `id` holding `plane` set, top to bottom,
 * summed to 1. Unchanged when the count does not match the column.
 */
export function setShares(desk: Desk, id: string, plane: string, shares: number[]): Desk {
	const strip = stripOf(desk, id);
	const at = strip && locate(strip, plane);
	if (!at) return desk;
	const col = strip.columns[at.column];
	if (shares.length !== col.panes.length || shares.some((s) => !(s > 0))) return desk;
	const d = draft(desk);
	(draftStrip(d, id) as Strip).columns[at.column].panes.forEach((p, i) => {
		p.share = shares[i];
	});
	return done(desk, d);
}

// -- Navigation, reset, save -------------------------------------------------

/**
 * Point the plane item `id`, or the pane of strip `id` showing `plane`, at
 * `link` through `set`. In a strip, a link to a plane another pane shows
 * focuses that pane and changes nothing.
 */
function point(desk: Desk, id: string, plane: string, link: Link, set: (x: Links) => void): Landed {
	const item = itemOf(desk, id);
	if (!item) return { desk, focus: "" };
	if (item.kind === "plane") {
		const d = draft(desk);
		set(itemOf(d, id) as PlaneItem);
		return { desk: done(desk, d), focus: link.plane };
	}
	const at = locate(item, plane);
	if (!at) return { desk, focus: "" };
	const other = locate(item, link.plane);
	if (other && (other.column !== at.column || other.pane !== at.pane)) {
		return { desk, focus: link.plane };
	}
	const d = draft(desk);
	set((draftStrip(d, id) as Strip).columns[at.column].panes[at.pane]);
	return { desk: done(desk, d), focus: link.plane };
}

/**
 * Navigate the plane item `id`, or the pane of strip `id` showing `plane`,
 * to `link`: it becomes the recent, or the recent goes when `link` is the
 * original. In a strip, a link to a plane another pane shows focuses that
 * pane instead, the navigating pane unchanged.
 */
export function navigate(desk: Desk, id: string, link: Link, plane = ""): Landed {
	return point(desk, id, plane, link, (x) => {
		x.recent = copyLink(link);
	});
}

/**
 * Reset the plane item `id`, or the pane of strip `id` showing `plane`, to
 * its original: the recent goes. In a strip, an original another pane shows
 * focuses that pane instead, nothing reset.
 */
export function reset(desk: Desk, id: string, plane = ""): Landed {
	const item = itemOf(desk, id);
	const x = item?.kind === "plane" ? item : item ? paneOf(item, plane) : null;
	if (!x?.recent) return { desk, focus: "" };
	return point(desk, id, plane, x.original, (y) => {
		delete y.recent;
	});
}

/** The plane item `id`, or its pane showing `plane`, saved: its recent made its original. */
export function save(desk: Desk, id: string, plane = ""): Desk {
	const linksIn = (d: Desk): Links | null => {
		const item = itemOf(d, id);
		return item?.kind === "plane" ? item : item ? paneOf(item, plane) : null;
	};
	if (!linksIn(desk)?.recent) return desk;
	const d = draft(desk);
	const x = linksIn(d) as Links;
	x.original = x.recent as Link;
	delete x.recent;
	return done(desk, d);
}
