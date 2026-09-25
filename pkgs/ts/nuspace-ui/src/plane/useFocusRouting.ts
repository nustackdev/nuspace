// Where the caret goes.
//
// Inside a cell's open source editor you get a caret. Across a cell
// boundary you get *cell* selection:
//
//   - Arrowing out of an editor's first or last line moves to the next cell
//   - If that cell is open in code mode, the caret enters it, carrying its
//     column
//   - Otherwise the cell gets *selected* and the plane takes keyboard focus
//   - Down or Enter at the end of the plane's title lands on the first cell

import { useCallback } from "react";
import type { PlaneModel } from "./model";
import type { FocusReq } from "./state";
import type { Cell, ExitDir } from "./types";

export function useFocusRouting({
	cells,
	editor,
	patch,
	index,
	rootRef,
	elRefs,
	endGhost,
	plusGhost,
}: PlaneModel) {
	const focusCell = useCallback(
		(cell: Cell, req: Omit<FocusReq, "cellId">, editing: string[]) => {
			if (editing.includes(cell.id)) {
				patch({
					focus: { cellId: cell.id, ...req },
					selected: [],
					anchor: null,
					column: null,
				});
				return;
			}
			// A cell with its source closed has no text for a caret to sit in.
			// Select it, and park the column so the next hop still lands under
			// the caret.
			patch({
				focus: null,
				selected: [cell.id],
				anchor: cell.id,
				column: req.column ?? null,
			});
			rootRef.current?.focus({ preventScroll: true });
			elRefs.current.get(cell.id)?.scrollIntoView({ block: "nearest" });
		},
		[patch, rootRef, elRefs],
	);

	/**
	 * Leave a cell vertically and land wherever is next.
	 *
	 * A ghost is not in `cells` -- it is not a cell -- but it IS in the
	 * document, between two rows or at the foot of the plane, so travel has to
	 * know about it or the last line on every plane would be unreachable from
	 * the keyboard. It carries no column: there is no text in it to land under.
	 */
	const step = useCallback(
		(fromId: string, dir: ExitDir, column: number | undefined) => {
			const i = index(fromId);
			if (i < 0) return;
			if (dir === "down") {
				if (editor.ghost === fromId) {
					plusGhost.current?.focus();
					return;
				}
				if (i === cells.length - 1) {
					endGhost.current?.focus();
					return;
				}
			} else if (i > 0 && editor.ghost === cells[i - 1].id) {
				plusGhost.current?.focus();
				return;
			}
			const j = dir === "up" ? i - 1 : i + 1;
			if (j < 0 || j >= cells.length) return;
			focusCell(cells[j], { place: dir === "up" ? "end" : "start", column }, editor.editing);
		},
		[cells, editor.editing, editor.ghost, focusCell, index, endGhost, plusGhost],
	);

	const enterCell = useCallback(
		(cell: Cell, place: "start" | "end" = "end") => {
			patch((e) => ({
				editing: e.editing.includes(cell.id) ? e.editing : [...e.editing, cell.id],
				focus: { cellId: cell.id, place },
				selected: [],
				anchor: null,
			}));
		},
		[patch],
	);

	/** Open or close a cell's source editor. The caret follows it open. */
	const setEditing = useCallback(
		(id: string, on: boolean) => {
			patch((e) => ({
				editing: on
					? e.editing.includes(id)
						? e.editing
						: [...e.editing, id]
					: e.editing.filter((x) => x !== id),
				focus: on ? { cellId: id, place: "end" } : e.focus,
			}));
		},
		[patch],
	);

	/** Select one cell and hand the keyboard to the plane. */
	const selectCell = useCallback(
		(id: string) => {
			patch({ selected: [id], anchor: id, focus: null });
			rootRef.current?.focus({ preventScroll: true });
		},
		[patch, rootRef],
	);

	/**
	 * Arrive from the title above: the first cell, or the end ghost on an
	 * empty plane. False when there is nothing to land in.
	 */
	const enterTop = useCallback((): boolean => {
		if (cells.length === 0) {
			const ghost = endGhost.current;
			if (!ghost) return false;
			ghost.focus();
			return true;
		}
		focusCell(cells[0], { place: "start" }, editor.editing);
		return true;
	}, [cells, editor.editing, focusCell, endGhost]);

	return { focusCell, step, enterCell, setEditing, selectCell, enterTop };
}
