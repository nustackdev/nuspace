// The plane layout, browser side, in plain functions: where a cell sits, the
// order the keyboard reads, and what a drop or a key sends.
//
// The layout is the server's (`nuspace/web/layout`), shipped fixed up with
// the cells (../types.ts `LayoutItem`): items top to bottom, each one cell
// alone or a strip of columns at their shares, cells stacked in a column.
// Nothing here writes it: every change is one `layout.*` event (../ops.ts),
// and the next `set_cells` draws what the server made of it.
//
// ## Reading order
//
// The plane core is a document: the caret, the selection and the input
// lines walk cells one after another. On a laid out plane that order is
// the layout's, item by item, a strip column by column (`readingOrder`), so
// Down from the last cell of a strip's first column goes to the top of the
// next column, and on past the strip.
//
// ## Drops (`dropOp`)
//
// A drag carries a cell (off its grip), and lands on a spot, read off the pointer as the target pane draws it
// (./drag.ts):
//
//   gap      between two items, `index` the item it lands before (the
//            count of items for the end)
//   side     the left or right of a cell: a cell alone becomes a strip with
//            it, a cell in a strip gets a new column on that side of its own
//   column   into a strip's column, `index` among its cells as drawn
//   end      the end of a plane, from its row in the sidebar
//
// The same plane:
//
//   cell item to a gap        layout.move of its item
//   cell of a strip to a gap  layout.place before / after an item
//   a cell to a side          layout.set of the target item, the strip made
//                             or regrouped here (the server takes the cell
//                             out of the item it leaves)
//   a cell into a column      layout.place into the strip; within its own
//                             strip a layout.set of the strip regrouped
//
// Another plane (a pane beside it, or a sidebar row): layout.transfer at the
// gap, into the column, or to the end. No side there: a strip is made where
// the cell already lives.
//
// A drop that changes nothing is null: no mark, nothing sent.

import { type Anchor, anchorAt } from "../../sidebar/ops";
import type { LayoutOp } from "../ops";
import type { LayoutColumn, LayoutItem, StoredItem, StripItem } from "../types";

/** What is being dragged: one cell, off its grip. */
export type Source = { kind: "cell"; plane: string; cell: string };

export type Side = "left" | "right";

/** Where a drag would land. Indices are as the target pane draws its layout. */
export type Spot =
	| { kind: "gap"; plane: string; index: number }
	| { kind: "side"; plane: string; cell: string; side: Side }
	| { kind: "column"; plane: string; item: string; column: number; index: number }
	| { kind: "end"; plane: string };

/** Where a cell sits: its item's position, and in a strip its column and place there. */
export type Seat = { at: number; item: LayoutItem; column: number; index: number };

// -- Reading ------------------------------------------------------------------

/** One cell item per cell, in order: the layout of a plane that ships none. */
export function plainLayout(cells: readonly { id: string }[]): LayoutItem[] {
	return cells.map((c) => ({ id: c.id, kind: "cell", cell: c.id }));
}

/** The cells an item holds, in reading order: a strip's column by column. */
export function itemCells(item: LayoutItem): string[] {
	return item.kind === "cell" ? [item.cell] : item.columns.flatMap((c) => c.cells);
}

/** Every cell of the layout, item by item, a strip column by column. */
export function readingOrder(layout: readonly LayoutItem[]): string[] {
	return layout.flatMap(itemCells);
}

/** `cells` in the layout's reading order. A cell it does not hold keeps last, in its order. */
export function inReadingOrder<T extends { id: string }>(
	cells: readonly T[],
	layout: readonly LayoutItem[],
): T[] {
	const at = new Map(readingOrder(layout).map((id, i) => [id, i]));
	const last = at.size;
	return [...cells].sort((a, b) => (at.get(a.id) ?? last) - (at.get(b.id) ?? last));
}

/** Where `cell` sits, null when no item holds it. */
export function seatOf(layout: readonly LayoutItem[], cell: string): Seat | null {
	for (let at = 0; at < layout.length; at++) {
		const item = layout[at];
		if (item.kind === "cell") {
			if (item.cell === cell) return { at, item, column: 0, index: 0 };
			continue;
		}
		for (let column = 0; column < item.columns.length; column++) {
			const index = item.columns[column].cells.indexOf(cell);
			if (index >= 0) return { at, item, column, index };
		}
	}
	return null;
}

/** The item `id` and where it is, null when the layout has none. */
function find(layout: readonly LayoutItem[], id: string): { at: number; item: LayoutItem } | null {
	const at = layout.findIndex((i) => i.id === id);
	return at < 0 ? null : { at, item: layout[at] };
}

/**
 * Where a cell made after `cell` belongs, when that is inside a strip: the
 * column under it. A cell is created on its own after the strip (the
 * server's fix-up), and this is where it is placed once it lands. Null
 * when `cell` is alone on its row, or is the plane's last cell, which an
 * end line writes after.
 */
export function spotUnder(
	layout: readonly LayoutItem[],
	cell: string,
): { into: string; column: number; index: number } | null {
	const seat = seatOf(layout, cell);
	if (seat?.item.kind !== "strip") return null;
	const order = readingOrder(layout);
	if (order[order.length - 1] === cell) return null;
	return { into: seat.item.id, column: seat.column, index: seat.index + 1 };
}

// -- Strips -------------------------------------------------------------------

/** What an op stores for `item`: the item without its id. */
export function stored(item: LayoutItem): StoredItem {
	return item.kind === "cell"
		? { kind: "cell", cell: item.cell }
		: {
				kind: "strip",
				columns: item.columns.map((c) => ({ cells: [...c.cells], share: c.share })),
			};
}

/** `columns` with no empty one, the shares left scaled back to sum 1 when one went. */
function pruned(columns: readonly LayoutColumn[]): LayoutColumn[] {
	const kept = columns.filter((c) => c.cells.length > 0);
	if (kept.length === columns.length) return kept;
	const total = kept.reduce((a, c) => a + c.share, 0);
	return kept.map((c) => ({ ...c, share: total > 0 ? c.share / total : 1 / kept.length }));
}

/** `columns` with `cell` taken out, by the strip rules: an empty column goes, the rest rescale. */
export function withoutCell(columns: readonly LayoutColumn[], cell: string): LayoutColumn[] {
	return pruned(columns.map((c) => ({ ...c, cells: c.cells.filter((id) => id !== cell) })));
}

/** `columns` with a new column of `cells` at `at`: it takes 1 / n of the width, the rest give it up in proportion. */
export function withColumn(
	columns: readonly LayoutColumn[],
	at: number,
	cells: string[],
): LayoutColumn[] {
	const n = columns.length + 1;
	const out = columns.map((c) => ({ ...c, share: (c.share * (n - 1)) / n }));
	out.splice(at, 0, { cells, share: 1 / n });
	return out;
}

/** Shares from sizes (any scale), summing to 1: the last takes what rounding left. */
export function sharesOf(sizes: readonly number[]): number[] {
	const total = sizes.reduce((a, s) => a + s, 0);
	if (!(total > 0)) return sizes.map(() => 1 / sizes.length);
	const out = sizes.map((s) => Math.round((s / total) * 1e6) / 1e6);
	out[out.length - 1] = 1 - out.slice(0, -1).reduce((a, s) => a + s, 0);
	return out;
}

/** Whether two share lists are the same, to within what a resize would mean. */
export function sameShares(a: readonly number[], b: readonly number[]): boolean {
	return a.length === b.length && a.every((s, i) => Math.abs(s - b[i]) < 1e-4);
}

/** Whether two column lists stack the same cells the same way, shares aside. */
function sameCells(a: readonly LayoutColumn[], b: readonly LayoutColumn[]): boolean {
	return (
		a.length === b.length &&
		a.every(
			(c, i) =>
				c.cells.length === b[i].cells.length && c.cells.every((id, j) => id === b[i].cells[j]),
		)
	);
}

/** `strip` resized: its columns at `shares`, or null when that is what it has. */
export function resized(strip: StripItem, shares: readonly number[]): LayoutOp | null {
	if (shares.length !== strip.columns.length) return null;
	const was = strip.columns.map((c) => c.share);
	if (sameShares(was, shares)) return null;
	const columns = strip.columns.map((c, i) => ({ cells: [...c.cells], share: shares[i] }));
	return { op: "layout.set", args: { item_id: strip.id, item: { kind: "strip", columns } } };
}

// -- Drops --------------------------------------------------------------------

const ids = (layout: readonly LayoutItem[]) => layout.map((i) => i.id);

/** `item` moved to gap `gap` of `layout`, where it stands at `at`. Null for its own gaps. */
function moveTo(
	layout: readonly LayoutItem[],
	id: string,
	at: number,
	gap: number,
): LayoutOp | null {
	if (gap === at || gap === at + 1) return null;
	const others = ids(layout).filter((i) => i !== id);
	return {
		op: "layout.move",
		args: { item_id: id, ...anchorAt(others, gap > at ? gap - 1 : gap) },
	};
}

/** A strip item writing `columns`, or null when it has the same cells as `was`. */
function regrouped(was: StripItem, columns: LayoutColumn[]): LayoutOp | null {
	if (sameCells(was.columns, columns)) return null;
	return { op: "layout.set", args: { item_id: was.id, item: { kind: "strip", columns } } };
}

/** A cell dropped beside `target`, all in one plane. */
function toSide(
	layout: readonly LayoutItem[],
	cell: string,
	target: string,
	side: Side,
): LayoutOp | null {
	if (cell === target) return null;
	const seat = seatOf(layout, target);
	if (!seat) return null;
	if (seat.item.kind === "cell") {
		const pair = side === "left" ? [cell, target] : [target, cell];
		const columns = pair.map((id) => ({ cells: [id], share: 0.5 }));
		return { op: "layout.set", args: { item_id: seat.item.id, item: { kind: "strip", columns } } };
	}
	const left = withoutCell(seat.item.columns, cell);
	const k = left.findIndex((c) => c.cells.includes(target));
	return regrouped(seat.item, withColumn(left, side === "left" ? k : k + 1, [cell]));
}

/** A cell dropped into column `column` of strip `strip` at `index` as drawn, all in one plane. */
function toColumn(
	layout: readonly LayoutItem[],
	cell: string,
	strip: string,
	column: number,
	index: number,
): LayoutOp | null {
	const found = find(layout, strip);
	if (found?.item.kind !== "strip" || !found.item.columns[column]) return null;
	const item = found.item;
	const from = seatOf(layout, cell);
	if (from?.item.id !== item.id) {
		return { op: "layout.place", args: { cell_id: cell, into: item.id, column, index } };
	}
	// Within its own strip: the whole strip regrouped, so a column it empties
	// going never shifts the one it lands in.
	const columns = item.columns.map((c) => ({ ...c, cells: [...c.cells] }));
	columns[from.column].cells.splice(from.index, 1);
	const at = from.column === column && from.index < index ? index - 1 : index;
	columns[column].cells.splice(Math.min(at, columns[column].cells.length), 0, cell);
	return regrouped(item, pruned(columns));
}

/**
 * What a drop of `source` on `spot` sends, or null for one that changes
 * nothing or is not offered. `from` is the source plane's layout, `to` the
 * target's (the same one within a plane).
 */
export function dropOp(
	source: Source,
	spot: Spot,
	from: readonly LayoutItem[],
	to: readonly LayoutItem[],
): LayoutOp | null {
	const same = source.plane === spot.plane;
	const cell = source.cell;
	if (!same) {
		const plane_id = spot.plane;
		let at: Anchor | { into: string; column: number; index: number };
		if (spot.kind === "gap") at = anchorAt(ids(to), spot.index);
		else if (spot.kind === "column")
			at = { into: spot.item, column: spot.column, index: spot.index };
		else if (spot.kind === "end") at = {};
		else return null;
		return { op: "layout.transfer", args: { cell_id: cell, plane_id, ...at } };
	}
	const seat = seatOf(from, cell);
	if (!seat) return null;
	if (spot.kind === "gap") {
		if (seat.item.kind === "cell") return moveTo(from, seat.item.id, seat.at, spot.index);
		return { op: "layout.place", args: { cell_id: cell, ...anchorAt(ids(from), spot.index) } };
	}
	if (spot.kind === "side") return toSide(from, cell, spot.cell, spot.side);
	if (spot.kind === "column") return toColumn(from, cell, spot.item, spot.column, spot.index);
	return null;
}

// -- Keys ---------------------------------------------------------------------

/**
 * The item order with the items holding `selected` moved one item up
 * (`dir` -1) or down, as a block. Null at the edge or for no selection.
 */
export function stepItems(
	layout: readonly LayoutItem[],
	selected: readonly string[],
	dir: -1 | 1,
): string[] | null {
	const sel = new Set(selected);
	const all = ids(layout);
	const picked = layout.filter((i) => itemCells(i).some((c) => sel.has(c))).map((i) => i.id);
	if (picked.length === 0) return null;
	const first = all.indexOf(picked[0]);
	const last = all.indexOf(picked[picked.length - 1]);
	if (dir < 0 ? first === 0 : last === all.length - 1) return null;
	const anchor = all[dir < 0 ? first - 1 : last + 1];
	const rest = all.filter((i) => !picked.includes(i));
	rest.splice(rest.indexOf(anchor) + (dir < 0 ? 0 : 1), 0, ...picked);
	return rest;
}

/**
 * The item order a new cell order asks for: each item where the first of
 * its cells now is. A strip moves as one, wherever its cells were sent.
 */
export function itemsInOrder(layout: readonly LayoutItem[], cells: readonly string[]): string[] {
	const at = new Map(cells.map((id, i) => [id, i]));
	const unsent = Number.MAX_SAFE_INTEGER;
	const first = (item: LayoutItem) => Math.min(...itemCells(item).map((c) => at.get(c) ?? unsent));
	return layout
		.map((item, i) => ({ id: item.id, key: first(item), i }))
		.sort((a, b) => a.key - b.key || a.i - b.i)
		.map((x) => x.id);
}
