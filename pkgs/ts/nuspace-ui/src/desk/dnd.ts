// The drag payloads every drop site shares, and the one call a drop makes.
//
// Three kinds of drag, each under its own type on the `DataTransfer`:
//
//   PLANE_MIME   a bare link, from the Planes tree or the nav section:
//                `{ plane, params }` as JSON (a bare plane id reads too)
//   ITEM_MIME    a desk item (a plane item or a strip): `{ desk, item }`
//   PANE_MIME    a pane of a strip, from its row or its header on the canvas:
//                `{ desk, item, plane }`
//
// A fourth, DESK_MIME, carries a desk id for reordering the folders; it is
// no drop for the table below.
//
// Where it lands (`Target`), from the sidebar or the canvas:
//
//   { kind: "end", desk }                  a desk title: the end of the desk
//   { kind: "between", desk, index }       between items in a folder
//   { kind: "onto", desk, item, side }     a plane item's row or canvas edge
//   { kind: "strip", desk, item, drop }    inside a strip (../desk/model.ts `Drop`)
//
// `planDrop` is the drag table of the task's iteration-3.md, pure: a link,
// item or pane between items is a plane item there (an item just moves);
// onto a plane item the two become a strip in its place; inside a strip it
// is a pane there. A dragged item or pane keeps its original and recent. A
// strip lands only between items. It answers the desks a drop writes, or
// null for a drop that does nothing, and that null is the one answer to
// "may this land here" (`canDrop`), for the sidebar and the canvas alike.
// `dropOn` writes the plan: one desk write per desk the gesture touches.
//
// A drop on a solo plane's edge, and a new desk made of a drag, are the same
// table on a desk not made yet (`planSolo`, `planNew`): written once, the new
// desk as a create.
//
// No DOM handlers here: the canvas and the sidebar own their pointer side.
// While dragging, a browser shows only the types on the drag, not the data,
// so the writers also note the drag here (`dragging`) for a drop site that
// needs to know what is coming. `endDrag` forgets it.

import { focusPane, knownDesks, openDesk, writeDesks } from "../core/router";
import type { Desk, Drop, Item, Link, Links, Side } from "./model";
import * as M from "./model";

/** A bare link dragged from the Planes tree or the nav section. */
export const PLANE_MIME = "application/x-nuspace-plane";

/** A desk item dragged by its row. */
export const ITEM_MIME = "application/x-nuspace-item";

/** A pane of a strip dragged by its row or its header. */
export const PANE_MIME = "application/x-nuspace-pane";

/**
 * A desk dragged by its folder's title, to reorder the desks: its id only,
 * and under its own type, so no drop site for planes takes it.
 */
export const DESK_MIME = "application/x-nuspace-desk";

/** What a drag carries. */
export type Payload =
	| { kind: "plane"; link: Link }
	| { kind: "item"; desk: string; item: string }
	| { kind: "pane"; desk: string; item: string; plane: string };

/** Where a drag lands. */
export type Target =
	| { kind: "end"; desk: string }
	| { kind: "between"; desk: string; index: number }
	| { kind: "onto"; desk: string; item: string; side: Side }
	| { kind: "strip"; desk: string; item: string; drop: Drop };

let current: Payload | null = null;

/** Put a bare link (or a plane id) on a drag. */
export function writePlane(data: DataTransfer, to: string | Link): void {
	const link = typeof to === "string" ? { plane: to, params: {} } : to;
	data.effectAllowed = "move";
	data.setData(PLANE_MIME, JSON.stringify(link));
	current = { kind: "plane", link };
}

/** Put item `item` of desk `desk` on a drag. */
export function writeItem(data: DataTransfer, desk: string, item: string): void {
	data.effectAllowed = "move";
	data.setData(ITEM_MIME, JSON.stringify({ desk, item }));
	current = { kind: "item", desk, item };
}

/** Put the pane showing `plane` in strip `item` of desk `desk` on a drag. */
export function writePane(data: DataTransfer, desk: string, item: string, plane: string): void {
	data.effectAllowed = "move";
	data.setData(PANE_MIME, JSON.stringify({ desk, item, plane }));
	current = { kind: "pane", desk, item, plane };
}

/** The kind of drag, off its types: readable while dragging. Null for anything else. */
export function dragKind(data: DataTransfer | null): Payload["kind"] | null {
	const types = data ? [...data.types] : [];
	if (types.includes(PANE_MIME)) return "pane";
	if (types.includes(ITEM_MIME)) return "item";
	if (types.includes(PLANE_MIME)) return "plane";
	return null;
}

function parse(raw: string): Record<string, unknown> | null {
	try {
		const v = JSON.parse(raw) as unknown;
		return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
	} catch {
		return null;
	}
}

const text = (v: unknown): v is string => typeof v === "string" && !!v;

/** What a drag carries, readable on drop only. Null for anything else or a bad payload. */
export function readDrag(data: DataTransfer | null): Payload | null {
	if (!data) return null;
	const pane = data.getData(PANE_MIME);
	if (pane) {
		const r = parse(pane);
		return r && text(r.desk) && text(r.item) && text(r.plane)
			? { kind: "pane", desk: r.desk, item: r.item, plane: r.plane }
			: null;
	}
	const item = data.getData(ITEM_MIME);
	if (item) {
		const r = parse(item);
		return r && text(r.desk) && text(r.item) ? { kind: "item", desk: r.desk, item: r.item } : null;
	}
	const plane = data.getData(PLANE_MIME);
	if (!plane) return null;
	if (!plane.startsWith("{")) return { kind: "plane", link: { plane, params: {} } };
	const r = parse(plane);
	if (!r || !text(r.plane)) return null;
	const params: Record<string, string> = {};
	if (r.params && typeof r.params === "object") {
		for (const [k, v] of Object.entries(r.params)) if (typeof v === "string") params[k] = v;
	}
	return { kind: "plane", link: { plane: r.plane, params } };
}

/** The drag this page started and has not ended, or null. */
export function dragging(): Payload | null {
	return current;
}

/** Forget the drag: on drag end. */
export function endDrag(): void {
	current = null;
}

// -- The drag table (pure) ----------------------------------------------------

/** What a drag carries once lifted: its links, the desk it leaves, and for an item move, the item. */
type Lifted = {
	links: Links;
	width?: number;
	from: { id: string; desk: Desk } | null;
	item: Item | null;
};

function lift(desks: Record<string, Desk>, payload: Payload): Lifted | null {
	if (payload.kind === "plane") {
		return { links: { original: payload.link }, from: null, item: null };
	}
	const source = desks[payload.desk];
	if (!source) return null;
	if (payload.kind === "item") {
		const taken = M.takeItem(source, payload.item);
		if (!taken) return null;
		const links =
			taken.item.kind === "plane" ? taken.item : { original: { plane: "", params: {} } };
		return {
			links,
			from: { id: payload.desk, desk: taken.desk },
			item: taken.item,
		};
	}
	const taken = M.takePane(source, payload.item, payload.plane);
	if (!taken) return null;
	return {
		links: taken.pane,
		width: taken.width,
		from: { id: payload.desk, desk: taken.desk },
		item: null,
	};
}

/**
 * The desks a drop writes, by id, or null when it does nothing (an unknown
 * desk, item or pane, a strip dragged anywhere but between items, a drop
 * onto itself, a plane the target strip shows already).
 */
export function planDrop(
	desks: Record<string, Desk>,
	payload: Payload,
	target: Target,
	random: () => number = Math.random,
): Record<string, Desk> | null {
	const into = desks[target.desk];
	if (!into) return null;
	// Within one item: a pane moved in its own strip, an item onto itself.
	if (payload.kind !== "plane" && payload.desk === target.desk) {
		if (target.kind === "strip" && payload.kind === "pane" && payload.item === target.item) {
			const next = M.movePane(into, target.item, payload.plane, target.drop);
			return next === into ? null : { [target.desk]: next };
		}
		if (payload.kind === "item") {
			if (target.kind !== "end" && target.kind !== "between") {
				if (payload.item === target.item) return null;
			} else {
				const index = target.kind === "end" ? into.items.length : target.index;
				const next = M.moveItem(into, payload.item, index);
				return next === into ? null : { [target.desk]: next };
			}
		}
	}
	const lifted = lift(desks, payload);
	if (!lifted) return null;
	const strip = lifted.item?.kind === "strip";
	if (strip && target.kind !== "end" && target.kind !== "between") return null;
	const same = lifted.from?.id === target.desk;
	const base = same && lifted.from ? lifted.from.desk : into;
	let next: Desk;
	if (target.kind === "end" || target.kind === "between") {
		// A pane leaves its strip in place, so the index as drawn still holds.
		const index = target.kind === "end" ? base.items.length : target.index;
		if (lifted.item) next = M.putItem(base, lifted.item, index, random);
		else {
			const id = M.mintItemId(base, random);
			next = M.addItem(base, { id, kind: "plane", ...lifted.links }, index);
		}
	} else if (target.kind === "onto") {
		next = M.makeStrip(base, target.item, lifted.links, target.side);
	} else {
		next = M.addPane(base, target.item, lifted.links, target.drop, lifted.width);
	}
	if (next === base) return null;
	if (same || !lifted.from) return { [target.desk]: next };
	return { [target.desk]: next, [lifted.from.id]: lifted.from.desk };
}

/**
 * Whether `payload` may land on `target`: whether the drag table writes
 * anything for it. A drag whose payload this page cannot read yet (another
 * window's) may: the drop decides.
 */
export function canDrop(payload: Payload | null, target: Target): boolean {
	const desks = knownDesks();
	return !payload || !desks || planDrop(desks, payload, target) !== null;
}

/**
 * The desks a drop on a solo plane's `side` edge writes: desk `id`, new, of
 * the solo plane and the dropped one side by side in a strip, and the desk
 * the dragged item or pane leaves. Null when no strip comes of it (the solo
 * plane itself, a whole strip).
 */
export function planSolo(
	desks: Record<string, Desk>,
	payload: Payload,
	solo: Link,
	side: Side,
	id: string,
	random: () => number = Math.random,
): Record<string, Desk> | null {
	const empty: Desk = { name: M.NEW_DESK_NAME, items: [] };
	const first = M.mintItemId(empty, random);
	const fresh = M.addItem(empty, { id: first, kind: "plane", original: solo }, 0);
	const plan = planDrop(
		{ ...desks, [id]: fresh },
		payload,
		{ kind: "onto", desk: id, item: first, side },
		random,
	);
	return plan?.[id]?.items[0]?.kind === "strip" ? plan : null;
}

/**
 * The desks a new desk `id` made of `payload` writes: the desk, named
 * "Untitled", holding it as its one item, and the desk a dragged item or
 * pane leaves. Null when nothing lands (an unknown item or pane).
 */
export function planNew(
	desks: Record<string, Desk>,
	payload: Payload,
	id: string,
	random: () => number = Math.random,
): Record<string, Desk> | null {
	const empty: Desk = { name: M.NEW_DESK_NAME, items: [] };
	return planDrop({ ...desks, [id]: empty }, payload, { kind: "end", desk: id }, random);
}

/** Whether a solo plane `plane` takes `payload` beside it (`planSolo`). */
export function canDropOnSolo(payload: Payload | null, plane: string): boolean {
	const desks = knownDesks();
	if (!payload || !desks) return true;
	return planSolo(desks, payload, { plane, params: {} }, "right", "") !== null;
}

/**
 * A drag dropped on a solo plane's `side` edge: the new desk of the two
 * (`planSolo`) written, opened with the dropped one focused.
 */
export function dropOnSolo(payload: Payload, solo: Link, side: Side): void {
	const desks = knownDesks();
	if (!desks) return;
	const id = M.mintDeskId((x) => !!desks[x]);
	const plan = planSolo(desks, payload, solo, side, id);
	if (!plan) return;
	writeDesks(plan);
	focusDropped(desks, payload, id, (plan[id].items[0] as M.Item).id);
	openDesk(id);
}

/** Focus the pane a drop of `payload` made in strip `item` of desk `desk`. */
function focusDropped(
	desks: Record<string, Desk>,
	payload: Payload,
	desk: string,
	item: string,
): void {
	const lifted = lift(desks, payload);
	if (lifted) focusPane(desk, item, M.shown(lifted.links).plane);
}

/**
 * A drag dropped on `target`: the drag table, written. A pane landing in a
 * strip, or a strip made from a plane item, is focused there.
 */
export function dropOn(payload: Payload, target: Target): void {
	const desks = knownDesks();
	const plan = desks && planDrop(desks, payload, target);
	if (!plan) return;
	writeDesks(plan);
	if (target.kind === "strip" || target.kind === "onto") {
		focusDropped(desks, payload, target.desk, target.item);
	}
}
