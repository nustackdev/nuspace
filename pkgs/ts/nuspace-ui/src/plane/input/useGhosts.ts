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
// A ghost opened with a way back (`home`, a focus target: where the caret
// was writing, or the cell a stand-in stands for) keeps it, and Escape takes
// it: the caret goes home as a focus request and a summoned ghost goes with
// it. Without one, Escape selects the cell the ghost hangs off.
//
// Typed text and Enter with the menu closed are offered to the sugar first
// (`route`, ../intents.ts). Unclaimed, text opens the menu with it as the
// query, and Enter does nothing. A claim that made a cell with a focus
// request leaves the request fed by this line (`line` on it, ../state.ts):
// the line shows its text and adds what is typed meanwhile, until the cell's
// document takes it.

import { useCallback, useRef } from "react";
import type { FocusTarget, PlaneModel } from "../api";
import type { InputIntent } from "../intents";
import type { FocusReq, InputLine } from "../state";
import type { Cell, ExitDir } from "../types";
import type { GhostProps } from "./Ghost";

export function useGhosts(
	{ cells, editor, patch, index, rootRef, endGhost, plusGhost }: PlaneModel,
	{
		focusCell,
		focus,
		select,
		drop,
		slashKey,
		route,
		hint,
	}: {
		focusCell: (cell: Cell, place: "start" | "end") => void;
		focus: (target: FocusTarget) => void;
		select: (ids: string[]) => void;
		drop: (gone: (r: FocusReq) => boolean) => void;
		slashKey: (key: string) => boolean;
		/** Offer an intent from line `line` after `after`. True when a sugar claimed it. */
		route: (after: string | null, i: InputIntent, line: InputLine) => boolean;
		/** The placeholder, from the sugar. Undefined: the core's own. */
		hint?: string;
	},
) {
	/** The way back from the ghost that is after `after`, while it holds the caret. */
	const back = useRef<{ after: string | null; to: FocusTarget } | null>(null);

	/**
	 * Open a line after `after` (null: at the top) and put the caret in it.
	 * Right below the last cell that is the end ghost, since a second empty
	 * line there would only make vertical travel pick between two. `home`
	 * is where Escape sends the caret; without one it selects the cell above.
	 */
	const openInput = useCallback(
		(after: string | null, home?: FocusTarget) => {
			back.current = home ? { after, to: home } : null;
			const last = cells.length ? cells[cells.length - 1].id : null;
			if (after === last) {
				patch({ ghost: null, slash: null });
				endGhost.current?.focus();
				return;
			}
			patch({ ghost: { after }, slash: null, selected: [], anchor: null });
		},
		[cells, endGhost, patch],
	);

	/**
	 * Stand in for cell `id` with the menu open: the cell hides, the ghost
	 * takes its place, and a pick replaces it. Put away with nothing picked,
	 * the cell comes back with the caret at its start.
	 */
	const standIn = useCallback(
		(id: string) => {
			back.current = { after: id, to: { cell: id, at: "start" } };
			patch({
				ghost: { after: id, replace: id },
				slash: null,
				selected: [],
				anchor: null,
			});
		},
		[patch],
	);

	/** The request line `line` feeds, changed by `f`. */
	const feed = useCallback(
		(line: InputLine, f: (r: FocusReq) => FocusReq) =>
			patch((e) =>
				e.requests.some((r) => r.line === line)
					? { requests: e.requests.map((r) => (r.line === line ? f(r) : r)) }
					: {},
			),
		[patch],
	);

	/** Nothing was picked. Close the menu, and take the offer back. A cell
	 *  this line was feeding still gets its text, without the caret. */
	const dismissGhost = useCallback(
		(after: string | null, transient: boolean) => {
			if (back.current?.after === after) back.current = null;
			patch(transient ? { ghost: null, slash: null } : { slash: null });
			feed(transient ? "summoned" : "end", (r) =>
				transient ? { ...r, pull: false, line: undefined } : { ...r, pull: false },
			);
		},
		[feed, patch],
	);

	/** Arrow out of a ghost into whichever cell is that way, if any. Up from
	 *  the top, into the title. */
	const leaveGhost = useCallback(
		(after: string | null, dir: ExitDir, transient: boolean) => {
			if (transient) patch({ ghost: null });
			const i = after ? index(after) : -1;
			const target = dir === "up" ? cells[i] : cells[i + 1];
			if (target) focusCell(target, dir === "up" ? "end" : "start");
			else if (dir === "up") focus({ title: "end" });
		},
		[cells, focus, focusCell, index, patch],
	);

	/** Escape with no menu open goes back where the ghost was opened from,
	 *  or else selects the cell it hangs off, since the ghost itself cannot
	 *  be one. A summoned ghost goes either way. */
	const escapeGhost = useCallback(
		(after: string | null, transient: boolean) => {
			const home = back.current?.after === after ? back.current.to : null;
			patch((e) => ({ slash: null, ghost: transient ? null : e.ghost }));
			if (home) {
				back.current = null;
				// A request, taken once the cell is drawn: a stand-in's cell is
				// back by then.
				focus(home);
				return;
			}
			select(after && index(after) >= 0 ? [after] : []);
			rootRef.current?.focus({ preventScroll: true });
		},
		[focus, index, patch, rootRef, select],
	);

	/**
	 * One ghost's props. `after` is both where it sits and who it is.
	 *
	 * A plain function rather than a memo: it takes arguments that only the
	 * render knows, and what it returns goes straight into an element.
	 */
	const ghostProps = (after: string | null, transient: boolean): GhostProps => {
		const standing = transient && editor.ghost?.replace != null;
		const line: InputLine = transient ? "summoned" : "end";
		const fed = editor.requests.find((r) => r.line === line);
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
			// The line shows the paragraph being typed: Enter starts another.
			pending: fed ? (fed.text ?? "").slice((fed.text ?? "").lastIndexOf("\n") + 1) : null,
			onWake: () => {
				// Clicking a ghost leaves cell-selection mode, exactly as
				// clicking into a cell does. The cell it feeds takes the caret
				// again when it lands.
				patch((e) => (e.selected.length ? { selected: [], anchor: null } : {}));
				feed(line, (r) => ({ ...r, pull: true }));
			},
			onOpenSlash: (anchor, query) =>
				patch({
					slash: { cellId: after, query, anchor, index: 0 },
					selected: [],
					anchor: null,
				}),
			onInput: (i, el) => {
				if (route(after, i, line)) return;
				if (i.kind === "text") {
					patch({
						slash: { cellId: after, query: i.text, anchor: el, index: 0 },
						selected: [],
						anchor: null,
					});
				}
			},
			onPending: (text) =>
				feed(line, (r) => {
					const was = r.text ?? "";
					return { ...r, text: was.slice(0, was.lastIndexOf("\n") + 1) + text };
				}),
			onBreak: () => feed(line, (r) => ({ ...r, text: `${r.text ?? ""}\n` })),
			onDrop: () => drop((r) => r.line === line),
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
	 *  with it, its cell coming back, and the caret stays where the press put
	 *  it rather than being pulled home. */
	const putAway = useCallback(() => {
		if (editor.ghost?.replace) {
			back.current = null;
			patch({ ghost: null, slash: null });
		} else patch((e) => (e.slash ? { slash: null } : {}));
	}, [editor.ghost, patch]);

	return { ghostProps, openInput, standIn, putAway };
}
