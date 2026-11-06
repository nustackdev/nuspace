// Which cell the caret is in, and the two things that follow from it.
//
// A cell's row says when the caret arrives in what the cell draws, elsewhere
// in the row, or leaves it (../cell/Cell.tsx). That is the row's own focus,
// heard the way any element hears it; nothing is read out of an editor.
//
// Hints. The document of a cell whose class has a sugar set with document
// hints (../sugar) draws them while the caret is in it, and stops as the
// caret leaves, so a hint is only ever on the line you are on. The set says
// what they read; setting and clearing them is the host's, here, through
// the document's own `hint`.
//
// A cell removed from under the caret, by another tab, a program or an
// agent: the caret goes to the end of the cell that was above it, else the
// title, the place R2 sends it when the person removes a blank one. Any
// remove from here moves the caret first, so by the time the server drops
// such a cell the caret is already somewhere else and this does nothing.

import { useCallback, useEffect, useRef } from "react";
import type { FocusTarget, PlaneModel } from "../api";
import { documentHint } from "../intents";
import type { Sugar } from "../sugar";
import type { Cell } from "../types";

export function useCaret(
	{ planeId, cells, read, document }: PlaneModel,
	{
		sugars,
		editable,
		focus,
	}: {
		sugars: readonly Sugar[];
		editable: boolean;
		focus: (target: FocusTarget) => void;
	},
) {
	/** The cell the caret is in, null when it is in none of this plane's. */
	const at = useRef<string | null>(null);
	/** The cells as the last render had them, to find what was above a gone one. */
	const was = useRef({ planeId, cells });

	/** The caret arrived in `cell`'s drawing ("ui"), elsewhere in its row, or left (null). */
	const caret = useCallback(
		(cell: Cell, where: "ui" | "row" | null) => {
			const hint = where === "ui" && editable ? documentHint(sugars, cell.classes) : undefined;
			const doc = document(cell.id);
			doc?.hint(hint?.blank ?? null, "blank");
			doc?.hint(hint?.tail ?? null, "tail");
			if (where) at.current = cell.id;
			else if (at.current === cell.id) at.current = null;
		},
		[document, editable, sugars],
	);

	useEffect(() => {
		const before = was.current;
		was.current = { planeId, cells };
		const id = at.current;
		if (!id || cells.some((c) => c.id === id)) return;
		at.current = null;
		// Another plane in this pane: the caret was not removed, the plane was swapped.
		if (before.planeId !== planeId) return;
		const { leaving } = read();
		const live = new Set(cells.filter((c) => !leaving.includes(c.id)).map((c) => c.id));
		const i = before.cells.findIndex((c) => c.id === id);
		const up = before.cells
			.slice(0, Math.max(i, 0))
			.reverse()
			.find((c) => live.has(c.id));
		focus(up ? { cell: up.id, at: "end" } : { title: "end" });
	}, [planeId, cells, read, focus]);

	return { caret };
}
