// The desk folders' state and their pure parts: what is folded, the rows a
// folder draws, which row is selected, and where a drop on a row lands.
// ./DeskFolders.tsx draws them. The order of the folders is the desks feed's
// (../core/desks.ts `useDeskOrder`: creation order, Favorites first).
//
// Folds: a folder, a strip row and a `Column` group fold. All are kept here,
// not in the section, because the body's one tab stop (./focus.ts) needs to
// know which rows are drawn. Kept across reloads under one key.
//
// Rows, top to bottom, the desk's items in order:
//
//   plane item   one row, at the folder's rows
//   strip        a `Strip` row, then one step in, per column: a pane row for
//                a column of one pane, a `Column` group row for 2+, its panes
//                one more step in, in stack order
//
// A pane is named by the plane it shows (a strip shows each plane once).
//
// Drops, by the pointer's band on the row (./drag.ts `edgeAt`: top quarter,
// middle half, bottom quarter), as a `Target` (../desk/dnd.ts):
//
//   plane item row     before / after: between items there; middle: onto
//                      it, the side by the pointer's half of the row (left
//                      half: the drag goes left of it, right half: right)
//   Strip row          before: between items there; middle: a new last
//                      column; after: open, a new first column, folded,
//                      between items after it
//   pane row, own      before / after: a new column there; middle: stacked
//   column             under that pane
//   Column group row   before: a new column there; middle: stacked at the
//                      column's bottom; after: open, stacked on top of the
//                      column, folded, a new column after it
//   pane row in a      before: stacked above it; middle and after: stacked
//   group              under it, except after the group's last pane, which
//                      is a new column after the group
//   folder title       the end of the desk
//
// The drop line's indent says which: at the folder's rows between items, one
// step in for a new column, two for a stack. A middle band rings the row.

import { readStored, writeStored } from "@nustackdev/ui-kit";
import { useSyncExternalStore } from "react";
import type { Target } from "../desk/dnd";
import type { Desk, Item, Links, Side } from "../desk/model";
import { locate, shown } from "../desk/model";
import type { DropEdge } from "./drag";

/** A folder title's fold key. */
export const folderKey = (desk: string) => `desk:${desk}`;

/** An item row's key, also a strip row's fold key. Never a tree row's (a plane id). */
export const itemKey = (desk: string, item: string) => `desk:${desk}:item:${item}`;

/** A `Column` group's row key, also its fold key. */
export const columnKey = (desk: string, item: string, column: number) =>
	`${itemKey(desk, item)}:column:${column}`;

/** A pane row's key. */
export const paneKey = (desk: string, item: string, plane: string) =>
	`${itemKey(desk, item)}:pane:${plane}`;

/** The title every strip row has. */
export const STRIP_TITLE = "Strip";

/** The title every column group has. */
export const COLUMN_TITLE = "Column";

/** A desk's name as its folder title shows it. */
export function deskLabel(name: string): string {
	return name.trim() || "Desk";
}

// -- Folds --------------------------------------------------------------------

const FOLDS_KEY = "nuspace.sidebar.desks.folded";

let folds: Set<string> | null = null;
const readers = new Set<() => void>();

function loadFolds(): Set<string> {
	if (folds) return folds;
	try {
		const raw = JSON.parse(readStored(FOLDS_KEY) ?? "[]");
		folds = new Set(Array.isArray(raw) ? raw.filter((k) => typeof k === "string") : []);
	} catch {
		folds = new Set();
	}
	return folds;
}

function subscribe(cb: () => void): () => void {
	readers.add(cb);
	return () => readers.delete(cb);
}

/** The folded folders, strips and column groups, by key. */
export function useFolds(): Set<string> {
	return useSyncExternalStore(subscribe, loadFolds, loadFolds);
}

/** Fold or unfold a folder, a strip or a column group. */
export function setFolded(key: string, folded: boolean): void {
	const now = loadFolds();
	if (now.has(key) === folded) return;
	const next = new Set(now);
	if (folded) next.add(key);
	else next.delete(key);
	folds = next;
	writeStored(FOLDS_KEY, JSON.stringify([...next]));
	for (const fn of [...readers]) fn();
}

/** Forget the folds. Tests only. */
export function resetFolders(): void {
	folds = null;
}

// -- Rows ---------------------------------------------------------------------

export type FolderRow =
	| { kind: "plane"; key: string; item: string; index: number; links: Links }
	| { kind: "strip"; key: string; item: string; index: number; open: boolean; columns: number }
	| {
			kind: "column";
			key: string;
			item: string;
			column: number;
			open: boolean;
			/** The planes the column shows, top to bottom. */
			planes: string[];
	  }
	| {
			kind: "pane";
			key: string;
			item: string;
			/** The plane the pane shows: what names it. */
			plane: string;
			links: Links;
			column: number;
			/** In a column group, two steps in; else one. */
			grouped: boolean;
			/** The last pane of its group. */
			last: boolean;
	  };

/** The row a folder row sits under: a pane's column group or strip, a column's strip. */
export function parentKey(desk: string, row: FolderRow): string | null {
	if (row.kind === "column") return itemKey(desk, row.item);
	if (row.kind === "pane") {
		return row.grouped ? columnKey(desk, row.item, row.column) : itemKey(desk, row.item);
	}
	return null;
}

/**
 * What Left or Right does on a folder row, as on a Planes tree row. On a
 * strip or column: Right unfolds a folded one and steps into an open one's
 * first row; Left folds an open one and climbs to the parent of a folded
 * one. On a plane item or pane: Left climbs to the parent, Right does nothing.
 * `next` is the row drawn under it.
 */
export function arrowMove(
	desk: string,
	row: FolderRow,
	arrow: "ArrowLeft" | "ArrowRight",
	next: FolderRow | undefined,
): { fold: true } | { focus: string } | null {
	const parent = parentKey(desk, row);
	const climb = parent ? { focus: parent } : null;
	if (row.kind === "strip" || row.kind === "column") {
		if (arrow === "ArrowRight") {
			if (!row.open) return { fold: true };
			return next ? { focus: next.key } : null;
		}
		return row.open ? { fold: true } : climb;
	}
	return arrow === "ArrowLeft" ? climb : null;
}

/** The rows desk `id` draws, top to bottom, given what is folded. */
export function folderRows(id: string, desk: Desk, folded: Set<string>): FolderRow[] {
	const out: FolderRow[] = [];
	desk.items.forEach((item, index) => {
		const key = itemKey(id, item.id);
		if (item.kind === "plane") {
			out.push({ kind: "plane", key, item: item.id, index, links: item });
			return;
		}
		const open = !folded.has(key);
		out.push({ kind: "strip", key, item: item.id, index, open, columns: item.columns.length });
		if (!open) return;
		item.columns.forEach((col, c) => {
			const pane = (links: Links, grouped: boolean, last: boolean): FolderRow => {
				const plane = shown(links).plane;
				const k = paneKey(id, item.id, plane);
				return { kind: "pane", key: k, item: item.id, plane, links, column: c, grouped, last };
			};
			if (col.panes.length < 2) {
				for (const p of col.panes) out.push(pane(p, false, true));
				return;
			}
			const ck = columnKey(id, item.id, c);
			const colOpen = !folded.has(ck);
			const planes = col.panes.map((p) => shown(p).plane);
			out.push({ kind: "column", key: ck, item: item.id, column: c, open: colOpen, planes });
			if (!colOpen) return;
			col.panes.forEach((p, i) => {
				out.push(pane(p, true, i === col.panes.length - 1));
			});
		});
	});
	return out;
}

/** The depth a row is drawn at. */
export function rowDepth(row: FolderRow): number {
	if (row.kind === "plane" || row.kind === "strip") return 0;
	if (row.kind === "column") return 1;
	return row.grouped ? 2 : 1;
}

// -- Selection ----------------------------------------------------------------

/**
 * The row of what the canvas shows, on desk `desk`: a plane item's row; in a
 * strip, the focused pane's row, or while that row is folded away, the
 * nearest row above it still drawn (its `Column` group, else the strip).
 */
export function selectedKey(desk: string, item: Item, focus: string, folded: Set<string>): string {
	const key = itemKey(desk, item.id);
	if (item.kind === "plane" || folded.has(key)) return key;
	const at = locate(item, focus);
	if (!at) return key;
	const col = item.columns[at.column];
	if (col.panes.length > 1 && folded.has(columnKey(desk, item.id, at.column))) {
		return columnKey(desk, item.id, at.column);
	}
	return paneKey(desk, item.id, focus);
}

// -- Drops --------------------------------------------------------------------

/** How a drop shows: a ring on the row, or a line before or after it at a depth. */
export type Mark = { ring: true } | { ring: false; edge: "before" | "after"; depth: number };

/** Where a drop on a row lands, and how it shows. */
export type Aim = { target: Target; mark: Mark };

const ring: Mark = { ring: true };
const line = (edge: "before" | "after", depth: number): Mark => ({ ring: false, edge, depth });

/**
 * Where a drop on `row` of desk `desk` at `band` lands. `side` is the
 * pointer's half of the row, for a drop onto a plane item.
 */
export function rowAim(desk: string, row: FolderRow, band: DropEdge, side: Side): Aim {
	const strip = (drop: Extract<Target, { kind: "strip" }>["drop"], mark: Mark): Aim => ({
		target: { kind: "strip", desk, item: row.item, drop },
		mark,
	});
	if (row.kind === "plane" || (row.kind === "strip" && (band === "before" || !row.open))) {
		if (band === "before") {
			return { target: { kind: "between", desk, index: row.index }, mark: line("before", 0) };
		}
		if (band === "after") {
			return { target: { kind: "between", desk, index: row.index + 1 }, mark: line("after", 0) };
		}
		if (row.kind === "plane") {
			return { target: { kind: "onto", desk, item: row.item, side }, mark: ring };
		}
	}
	if (row.kind === "strip") {
		if (band === "into") return strip({ at: row.columns }, ring);
		return strip({ at: 0 }, line("after", 1));
	}
	if (row.kind === "column") {
		if (band === "before") return strip({ at: row.column }, line("before", 1));
		if (band === "into") return strip({ column: row.column }, ring);
		return row.open && row.planes[0]
			? strip({ plane: row.planes[0], edge: "top" }, line("after", 2))
			: strip({ at: row.column + 1 }, line("after", 1));
	}
	if (row.kind === "pane") {
		if (!row.grouped) {
			if (band === "before") return strip({ at: row.column }, line("before", 1));
			if (band === "after") return strip({ at: row.column + 1 }, line("after", 1));
			return strip({ plane: row.plane, edge: "bottom" }, ring);
		}
		if (band === "before") return strip({ plane: row.plane, edge: "top" }, line("before", 2));
		if (band === "after" && row.last) return strip({ at: row.column + 1 }, line("after", 1));
		return strip({ plane: row.plane, edge: "bottom" }, band === "after" ? line("after", 2) : ring);
	}
	return strip({ at: 0 }, ring);
}

/** A drop on a folder title: the end of the desk. */
export function titleTarget(desk: string): Target {
	return { kind: "end", desk };
}
