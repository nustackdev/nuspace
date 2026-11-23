// The plane layout, browser side, in plain functions: where a cell sits, the
// order the keyboard reads, and the new rows a drop, a key, a resize or a
// create sends.
//
// The layout is the server's (`nuspace/web/layout`), shipped reconciled
// with the cells (../types.ts `LayoutRow`): rows top to bottom, each one
// cell alone or a strip of columns at their shares, cells stacked in a
// column. No row carries an id: a row is named by the first cell it holds
// (`rowKey`), a column by its place in its row. Every change is worked out
// here as the whole new rows and sent whole (../ops.ts `layout.set`, or
// `layout.transfer` / `cell.create` with them); the next `set_cells` draws
// what the server made of them, reconciled again there.
//
// Every function is pure: new rows out, the rows given left as they were.
//
// ## Reading order
//
// The plane core is a document: the caret, the selection and the input
// lines walk cells one after another. On a laid out plane that order is
// the layout's, row by row, a strip column by column (`readingOrder`), so
// Down from the last cell of a strip's first column goes to the top of the
// next column, and on past the strip.
//
// ## Drops (`dropOp`, `placed`)
//
// A drag carries a cell (off its grip), and lands on a spot, read off the
// pointer as the target pane draws it (./drag.ts):
//
//   gap      between two rows, `index` the row it lands before (the count
//            of rows for the end)
//   side     the left or right of a cell: a cell alone becomes a strip with
//            it, a cell in a strip gets a new column on that side of its own
//   column   into a strip's column, `index` among its cells as drawn
//   end      the end of a plane, from its row in the sidebar
//
// One rule for every spot, on the target's rows: the cell taken out where
// it was (by the strip rules), then put at the spot. Within the plane that
// is a `layout.set`; onto another open pane a `layout.transfer` with the
// target's rows (beside a cell there too); onto a sidebar row a plain
// `cell.transfer`, the server putting it last there. A drop that changes no
// cell's place is null: no mark, nothing sent.

import type { LayoutOp } from "../ops";
import type { LayoutColumn, LayoutRow } from "../types";

/** What is being dragged: one cell, off its grip. */
export type Source = { kind: "cell"; plane: string; cell: string };

export type Side = "left" | "right";

/** Where a drag would land. Indices are as the target pane draws its layout; a row is its key. */
export type Spot =
	| { kind: "gap"; plane: string; index: number }
	| { kind: "side"; plane: string; cell: string; side: Side }
	| { kind: "column"; plane: string; row: string; column: number; index: number }
	| { kind: "end"; plane: string };

/** Where a cell sits: its row's position, and in a strip its column and place there. */
export type Seat = { at: number; row: LayoutRow; column: number; index: number };

// -- Reading ------------------------------------------------------------------

/** One cell row per cell, in order: the layout of a plane that ships none. */
export function plainLayout(cells: readonly { id: string }[]): LayoutRow[] {
	return cells.map((c) => ({ kind: "cell", cell: c.id }));
}

/** The cells a row holds, in reading order: a strip's column by column. */
export function rowCells(row: LayoutRow): string[] {
	return row.kind === "cell" ? [row.cell] : row.columns.flatMap((c) => c.cells);
}

/** What names a row: its first cell. A cell sits in one row, so it is unique. */
export function rowKey(row: LayoutRow): string {
	return row.kind === "cell" ? row.cell : (row.columns[0]?.cells[0] ?? "");
}

/** Every cell of the layout, row by row, a strip column by column. */
export function readingOrder(layout: readonly LayoutRow[]): string[] {
	return layout.flatMap(rowCells);
}

/** `cells` in the layout's reading order. A cell it does not hold keeps last, in its order. */
export function inReadingOrder<T extends { id: string }>(
	cells: readonly T[],
	layout: readonly LayoutRow[],
): T[] {
	const at = new Map(readingOrder(layout).map((id, i) => [id, i]));
	const last = at.size;
	return [...cells].sort((a, b) => (at.get(a.id) ?? last) - (at.get(b.id) ?? last));
}

/** Where `cell` sits, null when no row holds it. */
export function seatOf(layout: readonly LayoutRow[], cell: string): Seat | null {
	for (let at = 0; at < layout.length; at++) {
		const row = layout[at];
		if (row.kind === "cell") {
			if (row.cell === cell) return { at, row, column: 0, index: 0 };
			continue;
		}
		for (let column = 0; column < row.columns.length; column++) {
			const index = row.columns[column].cells.indexOf(cell);
			if (index >= 0) return { at, row, column, index };
		}
	}
	return null;
}

/** Whether two layouts place every cell the same way, shares aside. */
export function sameCells(a: readonly LayoutRow[], b: readonly LayoutRow[]): boolean {
	const shape = (rows: readonly LayoutRow[]) =>
		JSON.stringify(rows.map((r) => (r.kind === "cell" ? r.cell : r.columns.map((c) => c.cells))));
	return shape(a) === shape(b);
}

// -- Strip rules ----------------------------------------------------------------

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

/** A row of `columns`: none for no cell, a cell row for one, else a strip. */
function rowOf(columns: LayoutColumn[]): LayoutRow | null {
	const held = columns.flatMap((c) => c.cells);
	if (held.length === 0) return null;
	if (held.length === 1) return { kind: "cell", cell: held[0] };
	return { kind: "strip", columns };
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

/** The rows with strip `key` at `shares`, or null when that is what it has. */
export function resized(
	layout: readonly LayoutRow[],
	key: string,
	shares: readonly number[],
): LayoutRow[] | null {
	const at = layout.findIndex((r) => rowKey(r) === key);
	const strip = layout[at];
	if (strip?.kind !== "strip" || shares.length !== strip.columns.length) return null;
	if (
		sameShares(
			strip.columns.map((c) => c.share),
			shares,
		)
	)
		return null;
	const columns = strip.columns.map((c, i) => ({ cells: [...c.cells], share: shares[i] }));
	return layout.map((r, i) => (i === at ? { kind: "strip", columns } : r));
}

// -- Placing one cell -----------------------------------------------------------

/** `layout` with `cell` taken out, by the strip rules. A row left empty is null, so positions keep. */
function takenOut(layout: readonly LayoutRow[], cell: string): (LayoutRow | null)[] {
	return layout.map((row) => {
		if (row.kind === "cell") return row.cell === cell ? null : row;
		if (!row.columns.some((c) => c.cells.includes(cell))) return row;
		return rowOf(withoutCell(row.columns, cell));
	});
}

const present = (rows: (LayoutRow | null)[]): LayoutRow[] =>
	rows.filter((r): r is LayoutRow => r !== null);

/**
 * `layout` with `cell` at `spot`, out of wherever it was. Null for a spot
 * that is not there, or that leaves every cell where it was. Works for a
 * cell of this plane and for one coming from another (which it holds
 * nowhere): the target's rows either way.
 */
export function placed(layout: readonly LayoutRow[], cell: string, spot: Spot): LayoutRow[] | null {
	const out = placedAt(layout, cell, spot);
	return out && !sameCells(out, layout) ? out : null;
}

function placedAt(layout: readonly LayoutRow[], cell: string, spot: Spot): LayoutRow[] | null {
	const alone: LayoutRow = { kind: "cell", cell };
	if (spot.kind === "end") return [...present(takenOut(layout, cell)), alone];
	if (spot.kind === "gap") {
		if (spot.index < 0 || spot.index > layout.length) return null;
		const rows = takenOut(layout, cell);
		rows.splice(spot.index, 0, alone);
		return present(rows);
	}
	if (spot.kind === "side") {
		if (spot.cell === cell) return null;
		const rows = takenOut(layout, cell);
		const at = rows.findIndex((r) => r !== null && rowCells(r).includes(spot.cell));
		const target = rows[at];
		if (!target) return null;
		if (target.kind === "cell") {
			const pair = spot.side === "left" ? [cell, target.cell] : [target.cell, cell];
			rows[at] = { kind: "strip", columns: pair.map((id) => ({ cells: [id], share: 0.5 })) };
		} else {
			const k = target.columns.findIndex((c) => c.cells.includes(spot.cell));
			const columns = withColumn(target.columns, spot.side === "left" ? k : k + 1, [cell]);
			rows[at] = { kind: "strip", columns };
		}
		return present(rows);
	}
	return intoColumn(layout, cell, spot.row, spot.column, spot.index);
}

/** `cell` into column `column` of strip `key` at `index` as drawn, out of wherever it was. */
function intoColumn(
	layout: readonly LayoutRow[],
	cell: string,
	key: string,
	column: number,
	index: number,
): LayoutRow[] | null {
	const at = layout.findIndex((r) => rowKey(r) === key);
	const strip = layout[at];
	if (strip?.kind !== "strip" || !strip.columns[column]) return null;
	// The strip's own columns with the cell out but none pruned yet, so a
	// column it empties going never shifts the one it lands in.
	const columns = strip.columns.map((c) => ({ ...c, cells: [...c.cells] }));
	const from = seatOf([strip], cell);
	if (from) columns[from.column].cells.splice(from.index, 1);
	const to = from && from.column === column && from.index < index ? index - 1 : index;
	const cells = columns[column].cells;
	cells.splice(Math.max(0, Math.min(to, cells.length)), 0, cell);
	const rows = takenOut(layout, cell);
	rows[at] = rowOf(pruned(columns));
	return present(rows);
}

/**
 * What a drop of `source` on `spot` sends, or null for one that changes
 * nothing or is not offered. `from` is the source plane's layout, `to` the
 * target's (the same one within a plane).
 */
export function dropOp(
	source: Source,
	spot: Spot,
	from: readonly LayoutRow[],
	to: readonly LayoutRow[],
): LayoutOp | null {
	const cell = source.cell;
	if (source.plane !== spot.plane) {
		const plane_id = spot.plane;
		if (spot.kind === "end") return { op: "cell.transfer", args: { cell_id: cell, plane_id } };
		const rows = placed(to, cell, spot);
		return rows ? { op: "layout.transfer", args: { cell_id: cell, plane_id, rows } } : null;
	}
	if (spot.kind === "end" || !seatOf(from, cell)) return null;
	const rows = placed(from, cell, spot);
	return rows ? { op: "layout.set", args: { rows } } : null;
}

// -- Creating -------------------------------------------------------------------

/**
 * `layout` with a new cell `cell` made after cell `after` (null: the top).
 * After a cell alone, its own row under it; after a cell in a strip, under
 * it in its column, at any depth; after the plane's last cell, its own row
 * at the end (the end line's create). An `after` no row holds is the end.
 */
export function withNewCell(
	layout: readonly LayoutRow[],
	cell: string,
	after: string | null,
): LayoutRow[] {
	const alone: LayoutRow = { kind: "cell", cell };
	if (after === null) return [alone, ...layout];
	const seat = seatOf(layout, after);
	const order = readingOrder(layout);
	if (!seat) return [...layout, alone];
	if (seat.row.kind === "cell" || order[order.length - 1] === after) {
		const rows = [...layout];
		rows.splice(seat.at + 1, 0, alone);
		return rows;
	}
	const columns = seat.row.columns.map((c, k) =>
		k === seat.column
			? {
					...c,
					cells: [...c.cells.slice(0, seat.index + 1), cell, ...c.cells.slice(seat.index + 1)],
				}
			: c,
	);
	return layout.map((r, i) => (i === seat.at ? { kind: "strip", columns } : r));
}

// -- Keys -----------------------------------------------------------------------

/**
 * The rows with those holding `selected` moved one row up (`dir` -1) or
 * down, as a block. Null at the edge or for no selection.
 */
export function stepRows(
	layout: readonly LayoutRow[],
	selected: readonly string[],
	dir: -1 | 1,
): LayoutRow[] | null {
	const sel = new Set(selected);
	const picked = layout.filter((r) => rowCells(r).some((c) => sel.has(c)));
	if (picked.length === 0) return null;
	const first = layout.indexOf(picked[0]);
	const last = layout.indexOf(picked[picked.length - 1]);
	if (dir < 0 ? first === 0 : last === layout.length - 1) return null;
	const anchor = layout[dir < 0 ? first - 1 : last + 1];
	const rest = layout.filter((r) => !picked.includes(r));
	rest.splice(rest.indexOf(anchor) + (dir < 0 ? 0 : 1), 0, ...picked);
	return rest;
}

/**
 * The rows a new cell order asks for: each row where the first of its cells
 * now is. A strip moves as one, wherever its cells were sent. Null when that
 * is the order they have.
 */
export function rowsInOrder(
	layout: readonly LayoutRow[],
	cells: readonly string[],
): LayoutRow[] | null {
	const at = new Map(cells.map((id, i) => [id, i]));
	const unsent = Number.MAX_SAFE_INTEGER;
	const first = (row: LayoutRow) => Math.min(...rowCells(row).map((c) => at.get(c) ?? unsent));
	const out = layout
		.map((row, i) => ({ row, key: first(row), i }))
		.sort((a, b) => a.key - b.key || a.i - b.i)
		.map((x) => x.row);
	return out.every((r, i) => r === layout[i]) ? null : out;
}
