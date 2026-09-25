// Text cells: the cells made from the text snippet, written like a document.
//
// A cell is a text cell when its `made_by` is TEXT, the name reserved for the
// text snippet, and a snippet by that name is registered. Nothing here
// knows what editor the snippet draws. The keys are caught on the cell's row
// in the capture phase, before the editor inside sees them, and only when
// they come from the cell's own editable surface (./Draft.tsx `cellSurface`):
//
//   - Cmd/Ctrl+Enter opens a ghost right below (./Ghost.tsx), and Escape
//	 there brings the caret back to where it stood.
//   - Backspace in an empty surface removes the cell, and the caret goes to
//     the end of the previous cell's surface, or selects the previous cell
//     when it has none.
//
// Enter in the title is the third way in, wired by the pane (see
// ../pane/Title.tsx). With no text snippet, none of it happens.

import type * as React from "react";
import { useCallback } from "react";
import { cellSurface, keepCaret, placeCaret, surfaceEmpty } from "./Draft";
import type { PlaneModel } from "./model";
import type { FocusReq } from "./state";
import { type Cell, hasText, type SlashSnippet, TEXT } from "./types";

export function useTextCells(
	{ planeId, cells, editor, notify, index, rootRef }: PlaneModel,
	snippets: SlashSnippet[],
	{
		focusCell,
		startDraft,
		openGhost,
	}: {
		focusCell: (cell: Cell, req: Omit<FocusReq, "cellId">, editing: string[]) => void;
		startDraft: ((after: string | null, text: string, caret?: number) => boolean) | null;
		openGhost: (after: string | null, home: (() => void) | null) => void;
	},
) {
	const on = hasText(snippets);

	const isText = useCallback((cell: Cell) => on && cell.made_by === TEXT, [on]);

	/** Take the caret off a cell that is going away: back to the one above. */
	const leaveUp = useCallback(
		(id: string) => {
			const prev = cells[index(id) - 1];
			if (!prev) {
				rootRef.current?.focus({ preventScroll: true });
				return;
			}
			const surface = cellSurface(rootRef.current, prev.id);
			if (surface) placeCaret(surface, "end");
			else focusCell(prev, { place: "end" }, editor.editing);
		},
		[cells, editor.editing, focusCell, index, rootRef],
	);

	/** A text cell's keys, caught on its row before its editor. */
	const textKey = useCallback(
		(e: React.KeyboardEvent, id: string) => {
			if (e.nativeEvent.isComposing || e.altKey || e.shiftKey) return;
			const surface = cellSurface(rootRef.current, id);
			if (!surface?.contains(e.target as Node)) return;
			const mod = e.metaKey || e.ctrlKey;
			if (e.key === "Enter" && mod) {
				e.preventDefault();
				e.stopPropagation();
				openGhost(id, keepCaret(rootRef.current, id));
				return;
			}
			if (e.key === "Backspace" && !mod && surfaceEmpty(surface)) {
				e.preventDefault();
				e.stopPropagation();
				leaveUp(id);
				notify("cell.delete", { plane_id: planeId, cell_id: id });
			}
		},
		[leaveUp, notify, openGhost, planeId, rootRef],
	);

	/** Enter mid-title: a text cell at the top holding `tail`, caret at its
	 *  start. False with no text snippet, or a draft already on its way. */
	const splitTitle = useCallback(
		(tail: string) => startDraft?.(null, tail, 0) ?? false,
		[startDraft],
	);

	/** Enter at the end of the title: a ghost at the top, Escape going back
	 *  to `home`. False with no text snippet. */
	const openTop = useCallback(
		(home: () => void) => {
			if (!on) return false;
			openGhost(null, home);
			return true;
		},
		[on, openGhost],
	);

	return { isText, textKey, splitTitle, openTop };
}
