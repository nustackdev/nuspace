// The ViewerRef node: what the wire writes, and all the browser-owned editor
// state.
//
// The wire half is every open Plane and its blocks, as a map by page id in
// `props.pages`: one entry replaced wholesale by that page's `set_page` and
// patched by its `set_status`. Entries for Planes no longer open are dropped.
//
// The browser half is caret intent, block selection, which blocks are open in
// code mode, the slash menu, the drag in flight. The server never sees
// any of it, none of it survives a reload, and none of it should. It lives in
// the node's `local` prop (see app/local.ts), as a map by page id, so each
// pane's selection, ghost, slash menu and code toggles are its own.
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
import { nodeAt, tree, useProps } from "@nustackdev/ui-kit";
import { useMemo } from "react";
import { LOCAL, localOf, patchLocal, useLocalSlot } from "../../app/local";
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

/** Every open Plane that has landed, by id, off the node's props. */
function pagesOf(props: Props): Record<string, ActivePage> {
	return (props.pages as Record<string, ActivePage> | undefined) ?? {};
}

/** Every pane's editor state, by Plane id, off the node's props. */
function panesOf(props: Props): Record<string, EditorState> {
	return localOf<Record<string, EditorState>>(props, {});
}

/** Keep only the entries for Planes in `open`. Same object when nothing goes. */
function keepOpen<T>(byId: Record<string, T>, open: string[]): Record<string, T> {
	const keys = Object.keys(byId);
	if (keys.every((k) => open.includes(k))) return byId;
	const out: Record<string, T> = {};
	for (const k of keys) if (open.includes(k)) out[k] = byId[k];
	return out;
}

/**
 * Apply one inbound payload to this node's props. Pure given `open`, the
 * Planes the URL names, so it is testable.
 *
 * Both ops are keyed by page. A `set_page` for a Plane that is no longer open
 * is a reply to a pane already closed and is dropped, and every write prunes
 * what belongs to closed panes.
 */
export function applyViewerWrite(props: Props, payload: unknown, open: string[]): void {
	const p = (payload ?? {}) as Record<string, unknown>;
	const op = String(p.op ?? "");
	const pageId = String(p.page_id ?? "");

	if (op === "set_status") {
		const pages = pagesOf(props);
		const page = pages[pageId];
		if (!page) return;
		const byId = new Map<string, SectionStatus>();
		for (const raw of Array.isArray(p.statuses) ? p.statuses : []) {
			const st = coerceStatus(raw);
			if (st?.section_id) byId.set(st.section_id, st);
		}
		if (byId.size === 0) return;
		props.pages = {
			...pages,
			[pageId]: {
				...page,
				blocks: page.blocks.map((b) =>
					byId.has(b.id) ? { ...b, status: byId.get(b.id) ?? b.status } : b,
				),
			} satisfies ActivePage,
		};
		return;
	}

	if (op !== "set_page") return;

	const pages = keepOpen(pagesOf(props), open);
	const panes = keepOpen(panesOf(props), open);
	if (!pageId || !open.includes(pageId)) {
		props.pages = pages;
		props.local = panes;
		return;
	}

	const blocks = coerceBlocks(p.blocks);
	props.pages = {
		...pages,
		[pageId]: {
			page_id: pageId,
			title: String(p.title ?? ""),
			editable: p.editable === true,
			blocks,
		} satisfies ActivePage,
	};

	// Prune local state that points at blocks which no longer exist. Focus and
	// drag are dropped outright -- a re-ship means the document moved under
	// them and guessing is worse than nothing.
	const live = new Set(blocks.map((b: Block) => b.id));
	const local = panes[pageId] ?? EMPTY_LOCAL;
	props.local = {
		...panes,
		[pageId]: {
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
		} satisfies EditorState,
	};
}

/**
 * Drop the pages and editor state of panes that are no longer open. Run when
 * the route changes, so a closed pane's data does not linger until the next
 * `set_page` happens to prune it.
 */
export function pruneViewer(path: Path, open: string[]): void {
	const node = nodeAt(path);
	if (!node) return;
	const pages = pagesOf(node.props);
	const panes = panesOf(node.props);
	const nextPages = keepOpen(pages, open);
	const nextPanes = keepOpen(panes, open);
	if (nextPages === pages && nextPanes === panes) return;
	tree.getState().setProps(path, { pages: nextPages, [LOCAL]: nextPanes });
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

const NO_PAGES: Record<string, ActivePage> = {};

export function useViewerValue(path: Path): ViewerValue {
	const props = useProps(path);
	const pages = (props.pages as Record<string, ActivePage> | undefined) ?? NO_PAGES;
	return useMemo(() => ({ pages }), [pages]);
}

/** One pane's editor state. Keyed by the Plane the pane shows. */
function paneOf(local: Record<string, EditorState>, pageId: string): EditorState {
	return local[pageId] ?? EMPTY_LOCAL;
}

const NO_PANES: Record<string, EditorState> = {};

export function useEditorState(path: Path, pageId: string): EditorState {
	return useLocalSlot(path, NO_PANES, (local) => paneOf(local, pageId));
}

/** Narrow subscription so a keystroke in one block does not rerender the rest. */
export function useEditorSlot<T>(path: Path, pageId: string, pick: (e: EditorState) => T): T {
	return useLocalSlot(path, NO_PANES, (local) => pick(paneOf(local, pageId)));
}

// -- writes ------------------------------------------------------------------

/**
 * Patch one pane's browser-owned editor state. Module-level rather than a
 * hook so event handlers deep in the tree can call it without prop-drilling,
 * and so it never participates in a render.
 */
export function patchEditor(
	path: Path,
	pageId: string,
	patch: Partial<EditorState> | ((e: EditorState) => Partial<EditorState>),
): void {
	patchLocal<Record<string, EditorState>>(path, NO_PANES, (local) => {
		const current = paneOf(local, pageId);
		const next = typeof patch === "function" ? patch(current) : patch;
		return { [pageId]: { ...current, ...next } };
	});
}
