// Wiring for the two ghost inputs (./Ghost.tsx).
//
// Both ghosts run the same handlers. What differs is where they sit and
// whether they are allowed to go away: the end-of-plane one is furniture, the
// summoned one is a passing offer. `after` is the cell a ghost would create
// past -- null only on a plane with no cells -- and it doubles as the ghost's
// identity, which is how the slash state can name one when neither of them
// has an id of its own.

import { useCallback } from "react";
import type { GhostProps } from "./Ghost";
import type { PlaneModel } from "./model";
import type { FocusReq } from "./state";
import type { Cell, ExitDir } from "./types";

export function useGhosts(
	{ cells, editor, patch, index, rootRef, endGhost, plusGhost }: PlaneModel,
	{
		focusCell,
		createAfter,
		slashKey,
		startDraft,
	}: {
		focusCell: (cell: Cell, req: Omit<FocusReq, "cellId">, editing: string[]) => void;
		createAfter: (afterId: string | null, name: string) => void;
		slashKey: (key: string) => boolean;
		startDraft: ((after: string | null, text: string) => void) | null;
	},
) {
	/** Nothing was picked. Close the menu, and take the offer back. */
	const dismissGhost = useCallback(
		(transient: boolean) => patch(transient ? { ghost: null, slash: null } : { slash: null }),
		[patch],
	);

	/** Arrow out of a ghost into whichever cell is that way, if any. */
	const leaveGhost = useCallback(
		(after: string | null, dir: ExitDir, transient: boolean) => {
			if (transient) patch({ ghost: null });
			const i = after ? index(after) : -1;
			const target = dir === "up" ? cells[i] : cells[i + 1];
			if (!target) return;
			focusCell(target, { place: dir === "up" ? "end" : "start" }, editor.editing);
		},
		[cells, editor.editing, focusCell, index, patch],
	);

	/** Escape with no menu open selects the cell the ghost hangs off, since
	 *  the ghost itself cannot be one. */
	const escapeGhost = useCallback(
		(after: string | null, transient: boolean) => {
			const cell = after ? cells[index(after)] : null;
			patch((e) => ({
				slash: null,
				ghost: transient ? null : e.ghost,
				selected: cell ? [cell.id] : [],
				anchor: cell ? cell.id : null,
				focus: null,
			}));
			rootRef.current?.focus({ preventScroll: true });
		},
		[cells, index, patch, rootRef],
	);

	/**
	 * One ghost's props. `after` is both where it sits and who it is.
	 *
	 * A plain function rather than a memo: it takes arguments that only the
	 * render knows, and what it returns goes straight into an element.
	 */
	const ghostProps = (after: string | null, transient: boolean): GhostProps => ({
		hostRef: transient ? plusGhost : endGhost,
		autoFocus: transient,
		query: editor.slash && editor.slash.cellId === after ? editor.slash.query : null,
		onWake: () => {
			// Clicking a ghost leaves cell-selection mode, exactly as
			// clicking into a cell does.
			patch((e) => (e.selected.length ? { selected: [], anchor: null } : {}));
		},
		onBlank: () => {
			patch({ slash: null, ghost: null });
			createAfter(after, "");
		},
		onOpenSlash: (anchor, query) =>
			patch({
				slash: { cellId: after, query, anchor, index: 0 },
				selected: [],
				anchor: null,
			}),
		onType: startDraft && ((text) => startDraft(after, text)),
		onQuery: (query) => patch((e) => (e.slash ? { slash: { ...e.slash, query, index: 0 } } : {})),
		onKey: slashKey,
		onCloseSlash: () => patch({ slash: null }),
		onEscape: () => escapeGhost(after, transient),
		onLeave: (dir) => leaveGhost(after, dir, transient),
		onDismiss: () => dismissGhost(transient),
	});

	return ghostProps;
}
