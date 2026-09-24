// A plane's browser-owned editor state.
//
// Caret intent, cell selection, which cells are open in code mode, the slash
// menu, the drag in flight. The server never sees any of it, none of it
// survives a reload, and none of it should. It lives in the ViewerRef node's
// `local` prop (see core/local.ts), as a map by plane id, so each pane's
// selection, ghost, slash menu and code toggles are its own.
//
// The node's wire half (the planes themselves) is ../main/state.ts, which also
// prunes this when a `set_plane` drops the cells it names.

import type { Path } from "@nustackdev/ui-core";
import { patchLocal, useLocalSlot } from "../core/local";

/** Where the caret should land next. Consumed by the cell that owns it. */
export type FocusReq = {
	cellId: string;
	/** Which end of the target editor to enter from. */
	place: "start" | "end";
	/**
	 * Desired column, carried across a cell boundary so arrowing down out of
	 * one cell and into the next lands under the caret rather than at
	 * column 0.
	 */
	column?: number;
};

export type SlashState = {
	/** The cell the ghost it is open on sits after. Null only on a plane
	 *  with no cells at all. */
	cellId: string | null;
	query: string;
	anchor: { x: number; y: number };
	index: number;
};

export type DragState = {
	id: string;
	/** Insertion index in the current cell list, 0..cells.length. */
	at: number;
	y: number;
};

export type EditorState = {
	focus: FocusReq | null;
	/**
	 * The cell that currently holds DOM focus, reported by the plane.
	 *
	 * Distinct from `focus`, which is an *intent* ("put the caret here") and
	 * is consumed and cleared the moment the target editor honours it. The
	 * gutter's focus rail wants the opposite: the standing fact of where the
	 * caret lives, for as long as it lives there.
	 */
	focused: string | null;
	selected: string[];
	/** Anchor for shift-extended cell selection. */
	anchor: string | null;
	/** Cells currently open in code mode. Per cell, never global. */
	editing: string[];
	slash: SlashState | null;
	/**
	 * The transient ghost input, as the id of the cell it sits after.
	 *
	 * Summoned by a gutter `+` and nothing else; it resolves into a cell or
	 * it goes away the moment it loses focus with nothing in it. At most one
	 * exists, because it is one id and not a set -- summoning a second while a
	 * first is open blurs the first, which is what dismisses it.
	 *
	 * The end-of-plane ghost is NOT here. It is always there, so there is
	 * nothing about it to remember.
	 */
	ghost: string | null;
	drag: DragState | null;
	/**
	 * Desired column, parked while the caret is "between" editors -- i.e.
	 * while a cell is merely *selected*. Without this the column resets every
	 * time vertical travel hops over a cell.
	 */
	column: number | null;
};

export const EMPTY_EDITOR: EditorState = {
	focus: null,
	focused: null,
	selected: [],
	anchor: null,
	editing: [],
	slash: null,
	ghost: null,
	drag: null,
	column: null,
};

export type EditorPatch = Partial<EditorState> | ((e: EditorState) => Partial<EditorState>);

/**
 * Drop everything in one pane's editor state that points at a cell not in
 * `live`. Focus and drag are dropped outright -- a re-ship means the document
 * moved under them and guessing is worse than nothing.
 */
export function pruneEditor(local: EditorState, live: Set<string>): EditorState {
	return {
		...local,
		focus: local.focus && live.has(local.focus.cellId) ? local.focus : null,
		focused: local.focused && live.has(local.focused) ? local.focused : null,
		selected: local.selected.filter((id) => live.has(id)),
		anchor: local.anchor && live.has(local.anchor) ? local.anchor : null,
		editing: local.editing.filter((id) => live.has(id)),
		// A null `cellId` is a ghost at the top of an empty plane, which no
		// cell list can invalidate.
		slash:
			local.slash && (local.slash.cellId === null || live.has(local.slash.cellId))
				? local.slash
				: null,
		ghost: local.ghost && live.has(local.ghost) ? local.ghost : null,
		drag: null,
	};
}

// -- Reads -------------------------------------------------------------------

/** One pane's editor state. Keyed by the Plane the pane shows. */
function paneOf(local: Record<string, EditorState>, planeId: string): EditorState {
	return local[planeId] ?? EMPTY_EDITOR;
}

const NO_PANES: Record<string, EditorState> = {};

export function useEditorState(path: Path, planeId: string): EditorState {
	return useLocalSlot(path, NO_PANES, (local) => paneOf(local, planeId));
}

// -- Writes ------------------------------------------------------------------

/**
 * Patch one pane's browser-owned editor state. Module-level rather than a
 * hook so event handlers deep in the tree can call it without prop-drilling,
 * and so it never participates in a render.
 */
export function patchEditor(path: Path, planeId: string, patch: EditorPatch): void {
	patchLocal<Record<string, EditorState>>(path, NO_PANES, (local) => {
		const current = paneOf(local, planeId);
		const next = typeof patch === "function" ? patch(current) : patch;
		return { [planeId]: { ...current, ...next } };
	});
}
