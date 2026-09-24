// A page's browser-owned editor state.
//
// Caret intent, block selection, which blocks are open in code mode, the slash
// menu, the drag in flight. The server never sees any of it, none of it
// survives a reload, and none of it should. It lives in the ViewerRef node's
// `local` prop (see app/local.ts), as a map by page id, so each pane's
// selection, ghost, slash menu and code toggles are its own.
//
// The node's wire half (the pages themselves) is ../main/state.ts, which also
// prunes this when a `set_page` drops the blocks it names.

import type { Path } from "@nustackdev/ui-core";
import { patchLocal, useLocalSlot } from "../app/local";

/** Where the caret should land next. Consumed by the block that owns it. */
export type FocusReq = {
	blockId: string;
	/** Which end of the target editor to enter from. */
	place: "start" | "end";
	/**
	 * Desired column, carried across a block boundary so arrowing down out of
	 * one block and into the next lands under the caret rather than at
	 * column 0.
	 */
	column?: number;
};

export type SlashState = {
	/** The block the ghost it is open on sits after. Null only on a page
	 *  with no blocks at all. */
	blockId: string | null;
	query: string;
	anchor: { x: number; y: number };
	index: number;
};

export type DragState = {
	id: string;
	/** Insertion index in the current block list, 0..blocks.length. */
	at: number;
	y: number;
};

export type EditorState = {
	focus: FocusReq | null;
	/**
	 * The block that currently holds DOM focus, reported by the page.
	 *
	 * Distinct from `focus`, which is an *intent* ("put the caret here") and
	 * is consumed and cleared the moment the target editor honours it. The
	 * gutter's focus rail wants the opposite: the standing fact of where the
	 * caret lives, for as long as it lives there.
	 */
	focused: string | null;
	selected: string[];
	/** Anchor for shift-extended block selection. */
	anchor: string | null;
	/** Blocks currently open in code mode. Per block, never global. */
	editing: string[];
	slash: SlashState | null;
	/**
	 * The transient ghost input, as the id of the block it sits after.
	 *
	 * Summoned by a gutter `+` and nothing else; it resolves into a block or
	 * it goes away the moment it loses focus with nothing in it. At most one
	 * exists, because it is one id and not a set -- summoning a second while a
	 * first is open blurs the first, which is what dismisses it.
	 *
	 * The end-of-page ghost is NOT here. It is always there, so there is
	 * nothing about it to remember.
	 */
	ghost: string | null;
	drag: DragState | null;
	/**
	 * Desired column, parked while the caret is "between" editors -- i.e.
	 * while a block is merely *selected*. Without this the column resets every
	 * time vertical travel hops over a block.
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
 * Drop everything in one pane's editor state that points at a block not in
 * `live`. Focus and drag are dropped outright -- a re-ship means the document
 * moved under them and guessing is worse than nothing.
 */
export function pruneEditor(local: EditorState, live: Set<string>): EditorState {
	return {
		...local,
		focus: local.focus && live.has(local.focus.blockId) ? local.focus : null,
		focused: local.focused && live.has(local.focused) ? local.focused : null,
		selected: local.selected.filter((id) => live.has(id)),
		anchor: local.anchor && live.has(local.anchor) ? local.anchor : null,
		editing: local.editing.filter((id) => live.has(id)),
		// A null `blockId` is a ghost at the top of an empty page, which no
		// block list can invalidate.
		slash:
			local.slash && (local.slash.blockId === null || live.has(local.slash.blockId))
				? local.slash
				: null,
		ghost: local.ghost && live.has(local.ghost) ? local.ghost : null,
		drag: null,
	};
}

// -- Reads -------------------------------------------------------------------

/** One pane's editor state. Keyed by the Plane the pane shows. */
function paneOf(local: Record<string, EditorState>, pageId: string): EditorState {
	return local[pageId] ?? EMPTY_EDITOR;
}

const NO_PANES: Record<string, EditorState> = {};

export function useEditorState(path: Path, pageId: string): EditorState {
	return useLocalSlot(path, NO_PANES, (local) => paneOf(local, pageId));
}

// -- Writes ------------------------------------------------------------------

/**
 * Patch one pane's browser-owned editor state. Module-level rather than a
 * hook so event handlers deep in the tree can call it without prop-drilling,
 * and so it never participates in a render.
 */
export function patchEditor(path: Path, pageId: string, patch: EditorPatch): void {
	patchLocal<Record<string, EditorState>>(path, NO_PANES, (local) => {
		const current = paneOf(local, pageId);
		const next = typeof patch === "function" ? patch(current) : patch;
		return { [pageId]: { ...current, ...next } };
	});
}
