// The plane's own keyboard: the cell-selection regime.
//
// Only live while at least one cell is selected. A focused editor (Monaco, a
// ghost) owns its keys outright and stops them before they reach the plane.

import type * as React from "react";
import { useCallback } from "react";
import type { PlaneModel } from "./model";
import type { FocusReq } from "./state";
import type { Cell } from "./types";

export function useCellKeys(
	{ cells, editor, patch }: PlaneModel,
	{
		focusCell,
		enterCell,
		deleteCells,
		moveSelected,
	}: {
		focusCell: (cell: Cell, req: Omit<FocusReq, "cellId">, editing: string[]) => void;
		enterCell: (cell: Cell) => void;
		deleteCells: (ids: string[]) => void;
		moveSelected: (dir: -1 | 1) => void;
	},
) {
	return useCallback(
		(e: React.KeyboardEvent) => {
			const sel = editor.selected;
			if (sel.length === 0) return;
			const ids = cells.map((b) => b.id);
			const first = ids.indexOf(sel[0]);
			const last = ids.indexOf(sel[sel.length - 1]);

			if (e.key === "Escape") {
				e.preventDefault();
				patch({ selected: [], anchor: null });
				return;
			}
			if (e.key === "Enter") {
				e.preventDefault();
				const b = cells[last];
				if (b) enterCell(b);
				return;
			}
			if (e.key === "Backspace" || e.key === "Delete") {
				e.preventDefault();
				deleteCells(sel);
				return;
			}
			if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "a") {
				e.preventDefault();
				patch({ selected: ids, anchor: ids[0] ?? null });
				return;
			}
			if (e.key === "ArrowUp" || e.key === "ArrowDown") {
				e.preventDefault();
				const dir = e.key === "ArrowUp" ? -1 : 1;
				if (e.metaKey || e.ctrlKey) {
					moveSelected(dir);
					return;
				}
				if (e.shiftKey) {
					const anchor = editor.anchor ?? sel[0];
					const a = ids.indexOf(anchor);
					const head = dir < 0 ? first - 1 : last + 1;
					if (head < 0 || head >= ids.length) return;
					const lo = Math.min(a, head);
					const hi = Math.max(a, head);
					patch({ selected: ids.slice(lo, hi + 1), anchor });
					return;
				}
				const j = dir < 0 ? first - 1 : last + 1;
				if (j < 0 || j >= ids.length) return;
				// Land the caret when the neighbour can hold one; otherwise the
				// selection just walks on, carrying the parked column with it.
				focusCell(
					cells[j],
					{ place: dir < 0 ? "end" : "start", column: editor.column ?? undefined },
					editor.editing,
				);
				return;
			}
		},
		[
			cells,
			deleteCells,
			editor.anchor,
			editor.column,
			editor.editing,
			editor.selected,
			enterCell,
			focusCell,
			moveSelected,
			patch,
		],
	);
}
