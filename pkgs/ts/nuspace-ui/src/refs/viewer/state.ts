// The ViewerRef node: what the wire writes, and all the browser-owned editor
// state.
//
// The wire half is the open Plane and its blocks, replaced wholesale by
// `set_page` and patched by `set_status`. It lands in props.
//
// The browser half is caret intent, block selection, which blocks are open in
// code mode, the slash menu, the drag in flight. The server never sees
// any of it, none of it survives a reload, and none of it should. It lives in
// the node's `local` prop (see app/local.ts).
//
// ## Blocks used to be registered here. They are not any more.
//
// This module used to build a slice per entry in a block's `fields` list, and
// reconcile them on every `set_page`. There is no fields list: a section's
// refs autovivify under the block's own address the first time something
// writes to one, and the store disposes a subtree when it goes. So all that
// is left of it is `blockUiPath` in ./blocks.ts, which is where a block's
// canvas looks for its ui.
//
// ## Why this type keeps a write handler
//
// Two ops ride one payload, told apart by an `op` key, and the store's default
// write has nothing to dispatch on. `set_status` also patches statuses into
// the block list by id, which a prop merge cannot do, and `set_page` has to
// prune local state naming blocks the new Plane does not carry, which nothing
// else is in a position to notice.

import type { Path, Props } from "@nustackdev/ui-core";
import { useProps } from "@nustackdev/ui-kit";
import { useMemo } from "react";
import { localOf, patchLocal, useLocalSlot } from "../../app/local";
import {
	type ActivePage,
	type Block,
	coerceBlocks,
	coerceStatus,
	type SectionStatus,
	type ViewerValue,
} from "./types";

// -- browser-owned editor state ----------------------------------------------

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
	 * The block that currently holds DOM focus, reported by the canvas.
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

export const EMPTY_LOCAL: EditorState = {
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

// -- the write handler's body ------------------------------------------------

/** Apply one inbound payload to this node's props. Pure, so it is testable. */
export function applyViewerWrite(props: Props, payload: unknown): void {
	const p = (payload ?? {}) as Record<string, unknown>;
	const op = String(p.op ?? "");

	if (op === "set_status") {
		const page = props.page as ActivePage | undefined;
		if (!page) return;
		const byId = new Map<string, SectionStatus>();
		for (const raw of Array.isArray(p.statuses) ? p.statuses : []) {
			const st = coerceStatus(raw);
			if (st?.section_id) byId.set(st.section_id, st);
		}
		if (byId.size === 0) return;
		props.page = {
			...page,
			blocks: page.blocks.map((b) =>
				byId.has(b.id) ? { ...b, status: byId.get(b.id) ?? b.status } : b,
			),
		} satisfies ActivePage;
		return;
	}

	if (op !== "set_page") return;

	const blocks = coerceBlocks(p.blocks);
	props.page = {
		page_id: String(p.page_id ?? ""),
		title: String(p.title ?? ""),
		editable: p.editable === true,
		blocks,
	} satisfies ActivePage;

	// Prune local state that points at blocks which no longer exist. Focus and
	// drag are dropped outright -- a re-ship means the document moved under
	// them and guessing is worse than nothing.
	const live = new Set(blocks.map((b: Block) => b.id));
	const local = localOf(props, EMPTY_LOCAL);
	props.local = {
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
	} satisfies EditorState;
}

// -- reads -------------------------------------------------------------------

/** One registered snippet, as the `/` menu offers it. */
export type SlashSnippet = { name: string; label: string };

const EMPTY_SNIPPETS: SlashSnippet[] = [];

/** The `/` menu's entries, in registry order, off the mount's props. */
export function useSnippets(path: Path): SlashSnippet[] {
	const raw = useProps(path).snippets;
	return useMemo(() => {
		if (!Array.isArray(raw)) return EMPTY_SNIPPETS;
		const out: SlashSnippet[] = [];
		for (const r of raw) {
			if (!r || typeof r !== "object") continue;
			const o = r as Record<string, unknown>;
			const name = typeof o.name === "string" ? o.name : "";
			if (!name) continue;
			const label = typeof o.label === "string" && o.label ? o.label : name;
			out.push({ name, label });
		}
		return out.length ? out : EMPTY_SNIPPETS;
	}, [raw]);
}

export function useViewerValue(path: Path): ViewerValue {
	const props = useProps(path);
	const page = (props.page as ActivePage | undefined) ?? null;
	return useMemo(() => ({ page }), [page]);
}

export function useEditorState(path: Path): EditorState {
	return useLocalSlot(path, EMPTY_LOCAL, (local) => local);
}

/** Narrow subscription so a keystroke in one block does not rerender the rest. */
export function useEditorSlot<T>(path: Path, pick: (e: EditorState) => T): T {
	return useLocalSlot(path, EMPTY_LOCAL, pick);
}

// -- writes ------------------------------------------------------------------

/**
 * Patch the browser-owned editor state. Module-level rather than a hook so
 * event handlers deep in the tree can call it without prop-drilling, and so
 * it never participates in a render.
 */
export function patchEditor(
	path: Path,
	patch: Partial<EditorState> | ((e: EditorState) => Partial<EditorState>),
): void {
	patchLocal(path, EMPTY_LOCAL, patch);
}
