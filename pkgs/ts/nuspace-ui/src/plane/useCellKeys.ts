// The plane's own keyboard: the cell-selection regime.
//
// Only live while at least one cell is selected. A focused editor (Monaco, a
// ghost) owns its keys outright and stops them before they reach the plane.
// On a read-only plane only Escape and copy do anything.

import type * as React from "react";
import { useCallback } from "react";
import type { PlaneModel } from "./model";
import type { FocusReq } from "./state";
import type { Cell } from "./types";

/**
 * Put the selected cells on the clipboard, in plane order: what each one
 * draws, as html and as plain text. A cell that draws nothing adds nothing.
 */
function copyCells(ids: string[], cells: Cell[], elRefs: PlaneModel["elRefs"]): void {
	const drawn = cells
		.filter((c) => ids.includes(c.id))
		.map((c) => elRefs.current.get(c.id)?.querySelector<HTMLElement>("[data-cell-ui]"))
		.filter((el): el is HTMLElement => el != null);
	const html = drawn.map((el) => el.innerHTML).join("");
	const plain = drawn.map((el) => el.innerText).join("\n");
	const clip = navigator.clipboard;
	if (!clip) return;
	if (typeof ClipboardItem === "undefined" || !clip.write) {
		clip.writeText(plain).catch(() => {});
		return;
	}
	const item = new ClipboardItem({
		"text/html": new Blob([html], { type: "text/html" }),
		"text/plain": new Blob([plain], { type: "text/plain" }),
	});
	clip.write([item]).catch(() => {});
}

export function useCellKeys(
	{ cells, editor, patch, elRefs }: PlaneModel,
	editable: boolean,
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
			if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "c") {
				// From an editor inside a cell, the copy is the editor's.
				if (e.target !== e.currentTarget) return;
				e.preventDefault();
				copyCells(sel, cells, elRefs);
				return;
			}
			if (!editable) return;
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
			editable,
			elRefs,
			enterCell,
			focusCell,
			moveSelected,
			patch,
		],
	);
}
