// Dragging cells: off a cell's grip, within a pane,
// onto another open pane, or onto a plane's row in the sidebar.
//
// A pointer drag, as the cell grip always was: the grip is also the button
// that opens the cell's menu, and a press that never travels past the kit's
// `CLICK_SLOP` is that click. Once it travels, every move reads what is
// under the pointer (`document.elementFromPoint`), so the drag crosses panes
// and the sidebar with no drop handlers of their own. The desk's drags are
// native HTML5 (../../desk/dnd.ts) and never see this one.
//
// What it aims at (`aimAt`):
//
//   a Planes tree row (`PLANE_ROW`)   the end of that plane, when it is one
//                                     the cell may go to: the source pane's
//                                     `cell.targets` answer, asked as the
//                                     drag starts (editable web planes, not
//                                     system, not removed). Its own plane,
//                                     or one not offered, rings refused
//   a pane (`data-pane`)              a spot in its plane (`spotIn`), read
//                                     off the rows as drawn, beside a cell
//                                     too. Another pane takes a cell only
//                                     when its plane does (`LAYOUT_TAKES`:
//                                     editable, not system)
//
// The spot becomes an op through ./model.ts `dropOp`: the whole new rows of
// the plane it lands on (`layout.set` within one, `layout.transfer` onto
// another pane), or a plain `cell.transfer` onto a sidebar row. Null draws
// no mark and sends nothing. One drag is in flight at most, kept here outside React
// (`useDragMark`, `useSidebarAim`, `useDragged`), so the source pane, the
// target pane and the sidebar each draw their own part of it. Escape drops
// the drag.
//
// Under the pointer, for the whole drag, rides the chip every drag shows
// (../../desk/drag.ts `dragChipOf`, the sidebar's and the pane headers'),
// saying "Cell". A native drag hands it to the browser as its image; this
// one carries it itself, and takes it away on drop or Escape.
//
// ## Where in a pane
//
// Against the rows the plane draws (`LAYOUT_ROW`), top to bottom:
//
//   between rows, above or under them     the gap there
//   a cell alone                          its left or right quarter: beside
//                                         it; its top or bottom half: the
//                                         gap above or under
//   a strip's top or bottom edge          the gap above or under it
//   a cell in a strip                     its left or right quarter: a new
//                                         column that side; its top or
//                                         bottom half: above or under it in
//                                         its column
//   a strip's column under its cells      the column's end

import type { Path } from "@nustackdev/ui-core";
import { CLICK_SLOP } from "@nustackdev/ui-kit";
import type * as React from "react";
import { useMemo, useSyncExternalStore } from "react";
import { CHIP_GRAB, dragChipOf } from "../../desk/drag";
import { clearPaneTargets, paneLayout, panePath, paneTargets } from "../../pane/state";
import { type LayoutOp, type Notify, sendOp } from "../ops";
import type { LayoutRow } from "../types";
import { dropOp, rowKey, type Side, type Source, type Spot, seatOf } from "./model";

/** On a plane's root: its id. Where a pane's layout is read from. */
export const LAYOUT_PLANE = "data-layout-plane";
/** On a plane's root when another plane's cells may land on it: editable, not system. */
export const LAYOUT_TAKES = "data-layout-takes";
/** On each row the plane draws: its key, its first cell. A cell alone carries it on its own row. */
export const LAYOUT_ROW = "data-layout-row";
/** On each column of a strip: its index. */
export const LAYOUT_COLUMN = "data-layout-column";
/** On each Planes tree row: its plane id. A cell dropped on it goes to that plane's end. */
export const PLANE_ROW = "data-plane-row";

/** The share of a cell's width, either side, that drops beside it. */
export const SIDE_BAND = 1 / 4;
/** How far in from a strip's top or bottom, px, a drop is the gap there. */
export const STRIP_EDGE = 8;

/** What the chip under a dragged cell says. */
export const CELL_CHIP = "Cell";

/** Why a sidebar row takes no cell. */
export const ALREADY_HERE = "Already on this plane";
export const NOT_A_TARGET = "Can't move here";

// -- Geometry (pure) ----------------------------------------------------------

type Box = { left: number; top: number; width: number; height: number };

/** The gap `y` falls in among `boxes` (top to bottom): before the first whose middle is under it. */
export function gapAt(boxes: readonly Box[], y: number): number {
	const i = boxes.findIndex((b) => b.height > 0 && y < b.top + b.height / 2);
	return i < 0 ? boxes.length : i;
}

/** Where on `box` a point is: a side quarter when `sides`, else its top or bottom half. */
export function zoneAt(box: Box, x: number, y: number, sides: boolean): Side | "top" | "bottom" {
	if (sides && box.width > 0) {
		const fx = (x - box.left) / box.width;
		if (fx < SIDE_BAND) return "left";
		if (fx > 1 - SIDE_BAND) return "right";
	}
	return y < box.top + box.height / 2 ? "top" : "bottom";
}

const within = (b: Box, y: number) => b.height > 0 && y >= b.top && y < b.top + b.height;

// -- Reading the pane under the pointer --------------------------------------

const boxOf = (el: Element): Box => el.getBoundingClientRect();

/** The cell's box (`data-cell-body`) in its row, the row's when it has none. */
function bodyOf(row: Element): Box {
	return boxOf(row.querySelector("[data-cell-body]") ?? row);
}

/** The spot in strip `strip` (row `at`) a point picks. */
function stripSpot(
	plane: string,
	strip: HTMLElement,
	at: number,
	x: number,
	y: number,
	sides: boolean,
): Spot {
	const box = boxOf(strip);
	if (y - box.top < STRIP_EDGE) return { kind: "gap", plane, index: at };
	if (box.top + box.height - y < STRIP_EDGE) return { kind: "gap", plane, index: at + 1 };
	const row = strip.getAttribute(LAYOUT_ROW) ?? "";
	const columns = [...strip.querySelectorAll<HTMLElement>(`[${LAYOUT_COLUMN}]`)];
	// The column under x, else the nearest one.
	let col = columns[0];
	let best = Number.POSITIVE_INFINITY;
	for (const c of columns) {
		const b = boxOf(c);
		const d = x < b.left ? b.left - x : x > b.left + b.width ? x - b.left - b.width : 0;
		if (d < best) {
			best = d;
			col = c;
		}
	}
	const column = Number(col?.getAttribute(LAYOUT_COLUMN) ?? 0);
	const rows = col ? [...col.querySelectorAll<HTMLElement>("[data-cell]")] : [];
	const boxes = rows.map(boxOf);
	const hit = boxes.findIndex((b) => within(b, y));
	if (hit >= 0) {
		const zone = zoneAt(bodyOf(rows[hit]), x, y, sides);
		if (zone === "left" || zone === "right") {
			return { kind: "side", plane, cell: rows[hit].dataset.cell ?? "", side: zone };
		}
		return { kind: "column", plane, row, column, index: zone === "top" ? hit : hit + 1 };
	}
	return { kind: "column", plane, row, column, index: gapAt(boxes, y) };
}

/** The spot a point picks in the plane drawn at `root`: `sides` offers the left and right of cells. */
export function spotIn(root: Element, plane: string, x: number, y: number, sides: boolean): Spot {
	const rows = [...root.querySelectorAll<HTMLElement>(`[${LAYOUT_ROW}]`)];
	const boxes = rows.map(boxOf);
	const at = boxes.findIndex((b) => within(b, y));
	if (at < 0) return { kind: "gap", plane, index: gapAt(boxes, y) };
	const el = rows[at];
	if (el.hasAttribute("data-cell")) {
		const zone = zoneAt(bodyOf(el), x, y, sides);
		if (zone === "left" || zone === "right") {
			return { kind: "side", plane, cell: el.dataset.cell ?? "", side: zone };
		}
		return { kind: "gap", plane, index: zone === "top" ? at : at + 1 };
	}
	return stripSpot(plane, el, at, x, y, sides);
}

// -- What a drag shows (pure) -------------------------------------------------

/** How a target pane marks a drop: a line on a cell, above a strip (by its key), or under the last row. */
export type Mark =
	| { kind: "above" | "below"; cell: string }
	| { kind: Side; cell: string; hint: string }
	| { kind: "strip"; row: string }
	| { kind: "end" };

/** What a hint beside a cell says. */
export const SIDE_BY_SIDE = "Side by side";
export const NEW_COLUMN = "New column";

/** The mark `spot` draws on the pane whose layout is `layout`. Null for none there (the sidebar's end). */
export function markOf(spot: Spot, layout: readonly LayoutRow[]): Mark | null {
	if (spot.kind === "gap") {
		const row = layout[spot.index];
		if (!row) return { kind: "end" };
		return row.kind === "cell"
			? { kind: "above", cell: row.cell }
			: { kind: "strip", row: rowKey(row) };
	}
	if (spot.kind === "side") {
		const seat = seatOf(layout, spot.cell);
		const hint = seat?.row.kind === "strip" ? NEW_COLUMN : SIDE_BY_SIDE;
		return { kind: spot.side, cell: spot.cell, hint };
	}
	if (spot.kind === "column") {
		const strip = layout.find((r) => rowKey(r) === spot.row);
		const cells = strip?.kind === "strip" ? (strip.columns[spot.column]?.cells ?? []) : [];
		if (cells.length === 0) return null;
		return spot.index < cells.length
			? { kind: "above", cell: cells[spot.index] }
			: { kind: "below", cell: cells[cells.length - 1] };
	}
	return null;
}

// -- The drag in flight -------------------------------------------------------

/** Where a drag is aimed: the spot, the op a drop sends, or why it is refused (a sidebar row). */
export type Aim = { spot: Spot; op: LayoutOp | null; refused: string | null };

type Now = { source: Source; aim: Aim | null; mark: Mark | null };

let now: Now | null = null;
const listeners = new Set<() => void>();

function set(next: Now | null): void {
	now = next;
	for (const l of listeners) l();
}

function subscribe(l: () => void): () => void {
	listeners.add(l);
	return () => listeners.delete(l);
}

/** The drag in flight, null for none. For tests and handlers. */
export function dragNow(): Now | null {
	return now;
}

/** The cell being dragged, "" for none. */
export function useDragged(): string {
	return useSyncExternalStore(subscribe, () => (now ? now.source.cell : ""));
}

/** The mark a drop on `plane` draws, null for none. */
export function useDragMark(plane: string): Mark | null {
	const key = useSyncExternalStore(subscribe, () =>
		now?.mark && now.aim?.spot.plane === plane ? JSON.stringify(now.mark) : "",
	);
	return useMemo(() => (key ? (JSON.parse(key) as Mark) : null), [key]);
}

/** A sidebar row a cell is aimed at: its plane, and why it is refused (null when it takes it). */
export type SidebarAim = { plane: string; refused: string | null };

/** The Planes tree row a cell drag is over, null for none. */
export function useSidebarAim(): SidebarAim | null {
	const key = useSyncExternalStore(subscribe, () => {
		const aim = now?.aim;
		if (aim?.spot.kind !== "end") return "";
		return JSON.stringify({ plane: aim.spot.plane, refused: aim.refused });
	});
	return useMemo(() => (key ? (JSON.parse(key) as SidebarAim) : null), [key]);
}

/** What a drag needs of the plane it starts on. */
export type DragFrom = {
	/** The ViewerRef node: every pane, and so every layout, hangs under it. */
	viewerPath: Path;
	/** The source pane's ops: a drop goes out here, a transfer too. */
	notify: Notify;
	/** The drag began (past the slop). */
	onStart?: () => void;
	/** The press never travelled: a click. */
	onClick?: () => void;
};

/** Where a drag of `source` at (`x`, `y`) is aimed, null for nowhere. */
export function aimAt(source: Source, viewerPath: Path, x: number, y: number): Aim | null {
	const el = document.elementFromPoint(x, y);
	if (!el) return null;
	const layoutOf = (plane: string) => paneLayout(panePath(viewerPath, plane)) ?? [];
	const row = el.closest(`[${PLANE_ROW}]`);
	if (row) {
		const plane = row.getAttribute(PLANE_ROW) ?? "";
		if (!plane) return null;
		const spot: Spot = { kind: "end", plane };
		if (plane === source.plane) return { spot, op: null, refused: ALREADY_HERE };
		const targets = paneTargets(panePath(viewerPath, source.plane));
		if (!targets) return null;
		if (!targets.some((t) => t.id === plane)) return { spot, op: null, refused: NOT_A_TARGET };
		const op = dropOp(source, spot, layoutOf(source.plane), []);
		return op ? { spot, op, refused: null } : null;
	}
	const root = el.closest("[data-pane]")?.querySelector(`[${LAYOUT_PLANE}]`);
	const plane = root?.getAttribute(LAYOUT_PLANE);
	if (!root || !plane) return null;
	if (plane !== source.plane && !root.hasAttribute(LAYOUT_TAKES)) return null;
	const spot = spotIn(root, plane, x, y, true);
	const op = dropOp(source, spot, layoutOf(source.plane), layoutOf(plane));
	return op ? { spot, op, refused: null } : null;
}

const sameAim = (a: Aim | null, b: Aim | null) => JSON.stringify(a) === JSON.stringify(b);

/**
 * Start a drag of `source` from a press on its grip. Past the slop it is a
 * drag: it asks for the cell's targets, aims on every move, and on release
 * sends the op its aim holds. Short of it, `onClick`.
 */
export function startDrag(e: React.PointerEvent, source: Source, from: DragFrom): void {
	if (e.button !== 0) return;
	e.preventDefault();
	(e.target as HTMLElement).setPointerCapture?.(e.pointerId);
	const x0 = e.clientX;
	const y0 = e.clientY;
	const body = document.body.style;
	const prevCursor = body.cursor;
	let on = false;
	let chip: HTMLElement | null = null;
	const carry = (x: number, y: number) => {
		if (!chip) return;
		chip.style.left = `${x - CHIP_GRAB}px`;
		chip.style.top = `${y - CHIP_GRAB}px`;
	};

	const aim = (x: number, y: number) => {
		if (!now) return;
		const next = aimAt(source, from.viewerPath, x, y);
		if (sameAim(now.aim, next)) return;
		const layout = next ? (paneLayout(panePath(from.viewerPath, next.spot.plane)) ?? []) : [];
		set({ source, aim: next, mark: next?.op ? markOf(next.spot, layout) : null });
	};
	const move = (ev: PointerEvent) => {
		if (!on) {
			if (Math.abs(ev.clientX - x0) < CLICK_SLOP && Math.abs(ev.clientY - y0) < CLICK_SLOP) return;
			on = true;
			body.cursor = "grabbing";
			set({ source, aim: null, mark: null });
			chip = dragChipOf(null, CELL_CHIP);
			// Over the panes and the sidebar, which stack above the page.
			chip.style.zIndex = "50";
			document.body.append(chip);
			clearPaneTargets(panePath(from.viewerPath, source.plane));
			from.notify("cell.targets", {});
			from.onStart?.();
		}
		carry(ev.clientX, ev.clientY);
		aim(ev.clientX, ev.clientY);
	};
	const stop = () => {
		window.removeEventListener("pointermove", move);
		window.removeEventListener("pointerup", up);
		window.removeEventListener("pointercancel", up);
		window.removeEventListener("keydown", key, true);
		body.cursor = prevCursor;
		chip?.remove();
		chip = null;
	};
	const up = (ev: PointerEvent) => {
		stop();
		if (!on) {
			if (ev.type === "pointerup") from.onClick?.();
			return;
		}
		const op = ev.type === "pointerup" ? now?.aim?.op : null;
		set(null);
		if (op) sendOp(from.notify, op);
	};
	const key = (ev: KeyboardEvent) => {
		if (ev.key !== "Escape" || !on) return;
		ev.preventDefault();
		ev.stopPropagation();
		stop();
		set(null);
	};
	window.addEventListener("pointermove", move);
	window.addEventListener("pointerup", up);
	window.addEventListener("pointercancel", up);
	window.addEventListener("keydown", key, true);
}
