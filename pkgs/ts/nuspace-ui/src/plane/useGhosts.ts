// Wiring for the two ghost inputs (./Ghost.tsx).
//
// Both ghosts run the same handlers. What differs is where they sit and
// whether they are allowed to go away: the end-of-plane one is furniture, the
// summoned one is a passing offer. `after` is the cell a ghost would create
// past -- null at the top of the plane, which the end one only is on a plane
// with no cells, where nothing is ever summoned -- and it doubles as the
// ghost's identity, which is how the slash state can name one when neither of
// them has an id of its own.
//
// A ghost opened from somewhere the caret was writing (Cmd+Enter in a text
// cell, `/` in an empty one) keeps the way back there, and Escape takes it:
// the caret goes home and a summoned ghost goes with it.

import { useCallback, useRef } from "react";
import { flushSync } from "react-dom";
import type { GhostProps } from "./Ghost";
import type { PlaneModel } from "./model";
import type { FocusReq } from "./state";
import type { Cell, ExitDir } from "./types";

export function useGhosts(
	{ cells, editor, patch, index, rootRef, endGhost, plusGhost }: PlaneModel,
	{
		focusCell,
		slashKey,
		startDraft,
		hint,
	}: {
		focusCell: (cell: Cell, req: Omit<FocusReq, "cellId">, editing: string[]) => void;
		slashKey: (key: string) => boolean;
		startDraft: ((after: string | null, text: string) => boolean) | null;
		/** The placeholder, from the sugar. Undefined: the core's own. */
		hint?: string;
	},
) {
	/** The way back from the ghost that is after `after`, while it holds the caret. */
	const back = useRef<{ after: string | null; to: () => void } | null>(null);

	/**
	 * Open a line after `after` (null: at the top) and put the caret in it.
	 * Right below the last cell that is the end ghost, since a second empty
	 * line there would only make vertical travel pick between two. `home`
	 * is where Escape sends the caret, null to select the cell above.
	 */
	const openGhost = useCallback(
		(after: string | null, home: (() => void) | null) => {
			back.current = home && { after, to: home };
			const last = cells.length ? cells[cells.length - 1].id : null;
			if (after === last) {
				patch({ ghost: null, slash: null });
				endGhost.current?.focus();
				return;
			}
			patch({ ghost: { after }, slash: null, selected: [], anchor: null, focus: null });
		},
		[cells, endGhost, patch],
	);

	/**
	 * Stand in for cell `id` with the menu open: the cell hides, the ghost
	 * takes its place, and a pick replaces it. `home` is where the caret goes
	 * back to when nothing is picked.
	 */
	const standIn = useCallback(
		(id: string, home: () => void) => {
			back.current = { after: id, to: home };
			patch({
				ghost: { after: id, replace: id },
				slash: null,
				selected: [],
				anchor: null,
				focus: null,
			});
		},
		[patch],
	);

	/** Nothing was picked. Close the menu, and take the offer back. */
	const dismissGhost = useCallback(
		(after: string | null, transient: boolean) => {
			if (back.current?.after === after) back.current = null;
			patch(transient ? { ghost: null, slash: null } : { slash: null });
		},
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

	/** Escape with no menu open goes back where the ghost was opened from,
	 *  or else selects the cell it hangs off, since the ghost itself cannot
	 *  be one. A summoned ghost goes either way. */
	const escapeGhost = useCallback(
		(after: string | null, transient: boolean) => {
			const home = back.current?.after === after ? back.current.to : null;
			if (home) {
				back.current = null;
				// Drawn now: a stand-in's cell has to be back before its caret.
				flushSync(() => patch((e) => ({ slash: null, ghost: transient ? null : e.ghost })));
				home();
				return;
			}
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
	const ghostProps = (after: string | null, transient: boolean): GhostProps => {
		const standing = transient && editor.ghost?.replace != null;
		return {
			hostRef: transient ? plusGhost : endGhost,
			autoFocus: transient,
			openMenu: standing,
			hint,
			// The summoned ghost owns the menu over the end one sitting after the same cell.
			query:
				editor.slash &&
				editor.slash.cellId === after &&
				(transient || editor.ghost?.after !== after)
					? editor.slash.query
					: null,
			onWake: () => {
				// Clicking a ghost leaves cell-selection mode, exactly as
				// clicking into a cell does.
				patch((e) => (e.selected.length ? { selected: [], anchor: null } : {}));
			},
			onOpenSlash: (anchor, query) =>
				patch({
					slash: { cellId: after, query, anchor, index: 0 },
					selected: [],
					anchor: null,
				}),
			onType: startDraft && ((text) => startDraft(after, text)),
			onQuery: (query) => patch((e) => (e.slash ? { slash: { ...e.slash, query, index: 0 } } : {})),
			// A stand-in is there for the menu: putting the menu away puts it away.
			onKey: (key) => {
				if (standing && key === "Escape") {
					escapeGhost(after, transient);
					return true;
				}
				return slashKey(key);
			},
			onCloseSlash: () => (standing ? escapeGhost(after, transient) : patch({ slash: null })),
			onEscape: () => escapeGhost(after, transient),
			onLeave: (dir) => leaveGhost(after, dir, transient),
			onDismiss: () => dismissGhost(after, transient),
		};
	};

	/** The menu was put away from outside (a press past it): a stand-in goes
	 *  with it, its cell coming back. */
	const putAway = useCallback(() => {
		const g = editor.ghost;
		if (g?.replace) escapeGhost(g.after, true);
		else patch((e) => (e.slash ? { slash: null } : {}));
	}, [editor.ghost, escapeGhost, patch]);

	return { ghostProps, openGhost, standIn, putAway };
}
