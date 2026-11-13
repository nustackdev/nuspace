// A plane's browser-owned editor state.
//
// Caret intent, cell selection, which cells are open in code mode, the slash
// menu, the drag in flight. The server never sees any of it, none of it
// survives a reload, and none of it should. It lives in the pane's own
// PaneRef node, in its `local` prop (see core/local.ts), so each pane's
// selection, ghost, slash menu and code toggles are its own, and a keystroke
// in one copies no other pane's state.
//
// The node's wire half (head, cells, statuses, trail) is ../pane/state.ts,
// which also prunes this when a `set_cells` drops the cells it names.

import type { Path } from "@nustackdev/ui-core";
import type { FocusAt } from "@nustackdev/ui-kit";
import { nodeAt } from "@nustackdev/ui-kit";
import { LOCAL, patchLocal, useLocalSlot } from "../core/local";

/**
 * Where the caret should land next, parked until the cell can take it.
 *
 * A request names a cell and who in it consumes it: the cell's markdown
 * editor (the kit's handle, see ./focus/useEditors.ts) or its open source
 * editor (./cell/Code.tsx). The consumer takes it when it is ready, the
 * markdown editor when it hands its handle and the source editor when it
 * has a view, and clears
 * it. A cell created a moment ago has neither yet, so the request simply
 * waits: there is no timeout, and Escape in the line that fed it drops it.
 *
 * Text and markdown ride along. `markdown` is appended to the document
 * before it is focused, `text` is typed in after, as the person's own
 * keystrokes, so it saves like any edit. What else the caller wants to hear
 * (the handle that took it) is not serialisable, so it is kept beside
 * this state by `id` (./focus/useFocusRouting.ts), never in it.
 */
export type FocusReq = {
	/** Names the request, and the hook kept beside it, if any. */
	id: number;
	cellId: string;
	/** Who consumes it: the cell's markdown editor ("document"), or its open source editor. */
	to: "document" | "source";
	at: FocusAt;
	/**
	 * Desired column, carried across a cell boundary so arrowing down out of
	 * one source and into the next lands under the caret rather than at
	 * column 0. Sources only.
	 */
	column?: number;
	/** Appended to the document before it is focused. */
	markdown?: string;
	/** Typed into the document once it has the caret, as if at the keyboard. */
	text?: string;
	/**
	 * It takes the caret when consumed. Dropped to false once the person put
	 * the caret somewhere else meanwhile: what it carries still lands, the
	 * caret stays where they put it.
	 */
	pull: boolean;
	/** Its markdown editor takes commands: it is consumed once the cell is drawn. */
	ready?: boolean;
	/** For a cell asked for and not shipped back yet, which pruning keeps. */
	fresh?: boolean;
	/**
	 * The input line feeding it, which shows `text` and takes the keys typed
	 * meanwhile until it lands: the end line, or the summoned one.
	 */
	line?: InputLine;
};

/** The two input lines a plane can have: always one at the end, at most one summoned. */
export type InputLine = "end" | "summoned";

export type SlashState = {
	/** The cell the ghost it is open on sits after. Null only on a plane
	 *  with no cells at all. */
	cellId: string | null;
	query: string;
	anchor: SlashAnchor;
	index: number;
};

/** The line the menu opened from: the ghost's input, which the menu stays
 *  pinned to while the page scrolls. */
export type SlashAnchor = HTMLElement;

export type DragState = {
	id: string;
	/** Insertion index in the current cell list, 0..cells.length. */
	at: number;
	y: number;
};

export type EditorState = {
	/** Focus requests waiting for their cell, oldest first. At most one pulls. */
	requests: FocusReq[];
	selected: string[];
	/** Anchor for shift-extended cell selection. */
	anchor: string | null;
	/** Cells currently open in code mode. Per cell, never global. */
	editing: string[];
	slash: SlashState | null;
	/**
	 * The transient ghost input, as the id of the cell it sits after, null
	 * at the top of the plane.
	 *
	 * Summoned by a gutter `+`, or by a sugar (../sugar); it resolves into a cell or it goes away the moment it loses focus
	 * with nothing in it. At most one exists, because it is one
	 * slot and not a set -- summoning a second while a first is open blurs the
	 * first, which is what dismisses it.
	 *
	 * The end-of-plane ghost is NOT here. It is always there, so there is
	 * nothing about it to remember.
	 *
	 * `replace` makes it a stand-in: it sits in place of that cell, which
	 * hides while it is up, opens with the menu open, and a pick replaces the
	 * cell. Put away with nothing picked, the cell comes back as it was.
	 */
	ghost: { after: string | null; replace?: string } | null;
	/**
	 * Cells deleted from here that the server has not dropped yet: hidden
	 * until it does, so a replaced cell never flashes back for a round trip.
	 */
	leaving: string[];
	drag: DragState | null;
	/**
	 * Desired column, parked while the caret is "between" editors -- i.e.
	 * while a cell is merely *selected*. Without this the column resets every
	 * time vertical travel hops over a cell.
	 */
	column: number | null;
	/**
	 * Text an input line holds again, by line: what it had fed a new cell
	 * that turned out never to take it (no document, or a program that died).
	 * Plain typing in the line from here; the next key goes on from it.
	 */
	held: Partial<Record<InputLine, string>>;
};

export const EMPTY_EDITOR: EditorState = {
	requests: [],
	selected: [],
	anchor: null,
	editing: [],
	slash: null,
	ghost: null,
	leaving: [],
	drag: null,
	column: null,
	held: {},
};

export type EditorPatch = Partial<EditorState> | ((e: EditorState) => Partial<EditorState>);

/**
 * Drop everything in one pane's editor state that points at a cell not in
 * `live`. Drag is dropped outright -- a re-ship means the document moved
 * under it and guessing is worse than nothing. A focus request for a cell
 * asked for here and not shipped yet stays: the cell is on its way, and the
 * first `set_cells` that carries it makes it an ordinary request.
 */
export function pruneEditor(local: EditorState, live: Set<string>): EditorState {
	return {
		...local,
		requests: (local.requests ?? []).flatMap((r) =>
			live.has(r.cellId) ? [r.fresh ? { ...r, fresh: false } : r] : r.fresh ? [r] : [],
		),
		selected: local.selected.filter((id) => live.has(id)),
		anchor: local.anchor && live.has(local.anchor) ? local.anchor : null,
		editing: local.editing.filter((id) => live.has(id)),
		leaving: (local.leaving ?? []).filter((id) => live.has(id)),
		// A null `cellId` is a ghost at the top of an empty plane, which no
		// cell list can invalidate.
		slash:
			local.slash && (local.slash.cellId === null || live.has(local.slash.cellId))
				? local.slash
				: null,
		// A ghost at the top needs a cell under it, or it is the end ghost's twin.
		ghost:
			local.ghost && (local.ghost.after === null ? live.size > 0 : live.has(local.ghost.after))
				? local.ghost
				: null,
		drag: null,
	};
}

// -- Reads -------------------------------------------------------------------

/** The pane's editor state, off its PaneRef node. */
export function useEditorState(panePath: Path): EditorState {
	return useLocalSlot(panePath, EMPTY_EDITOR, (local) => local);
}

/** The pane's editor state as it is now, outside a render: for a handler
 *  that patched a moment ago and must not act on the render's copy. */
export function readEditor(panePath: Path): EditorState {
	return (nodeAt(panePath)?.props[LOCAL] as EditorState | undefined) ?? EMPTY_EDITOR;
}

// -- Writes ------------------------------------------------------------------

/**
 * Patch the pane's browser-owned editor state. Module-level rather than a
 * hook so event handlers deep in the tree can call it without prop-drilling,
 * and so it never participates in a render. A pane whose node has not
 * landed has no state to patch.
 */
export function patchEditor(panePath: Path, patch: EditorPatch): void {
	patchLocal<EditorState>(panePath, EMPTY_EDITOR, (current) =>
		typeof patch === "function" ? patch(current) : patch,
	);
}
