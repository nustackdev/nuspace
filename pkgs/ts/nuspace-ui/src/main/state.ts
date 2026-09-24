// The ViewerRef node: what the wire writes into it.
//
// Every open Plane and its blocks, as a map by page id in `props.pages`: one
// entry replaced wholesale by that page's `set_page` and patched by its
// `set_status`. Entries for Planes no longer open are dropped. The browser half
// of the node (each pane's editor state) is ../page/state.ts.
//
// ## Blocks are not registered here
//
// A section's refs autovivify under the block's own address the first time
// something writes to one, and the store disposes a subtree when it goes. All
// the browser knows about that address is ../page/block/address.ts.
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
import { LOCAL, localOf } from "../app/local";
import { type EditorState, EMPTY_EDITOR, pruneEditor } from "../page/state";
import {
	type ActivePage,
	coerceBlocks,
	coerceMeta,
	coerceStatus,
	type SectionStatus,
	type SlashSnippet,
} from "../page/types";

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

// -- The write handler's body ------------------------------------------------

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
		props[LOCAL] = panes;
		return;
	}

	const blocks = coerceBlocks(p.blocks);
	props.pages = {
		...pages,
		[pageId]: {
			page_id: pageId,
			title: String(p.title ?? ""),
			meta: coerceMeta(p.meta),
			blocks,
		} satisfies ActivePage,
	};

	const live = new Set(blocks.map((b) => b.id));
	props[LOCAL] = { ...panes, [pageId]: pruneEditor(panes[pageId] ?? EMPTY_EDITOR, live) };
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

/**
 * Merge `meta` into one page's settings, locally. The optimistic half of a
 * `page.meta`: the switch moves now, and the server's next `set_page`
 * replaces the whole page with what it actually stored.
 */
export function patchPageMeta(path: Path, pageId: string, meta: Record<string, unknown>): void {
	const node = nodeAt(path);
	if (!node) return;
	const pages = pagesOf(node.props);
	const page = pages[pageId];
	if (!page) return;
	tree.getState().setProps(path, {
		pages: { ...pages, [pageId]: { ...page, meta: coerceMeta({ ...page.meta, ...meta }) } },
	});
}

/**
 * Set one page's title, locally. The optimistic half of a rename from a tab:
 * the tab and the page's heading change now, and the server's next
 * `set_page` replaces the page with what it actually stored.
 */
export function patchPageTitle(path: Path, pageId: string, title: string): void {
	const node = nodeAt(path);
	if (!node) return;
	const pages = pagesOf(node.props);
	const page = pages[pageId];
	if (!page || page.title === title) return;
	tree.getState().setProps(path, { pages: { ...pages, [pageId]: { ...page, title } } });
}

// -- Reads -------------------------------------------------------------------

const NO_PAGES: Record<string, ActivePage> = {};

/** Every open Plane that has landed, by id. A pane whose id is missing is
 *  still loading. */
export function usePages(path: Path): Record<string, ActivePage> {
	return (useProps(path).pages as Record<string, ActivePage> | undefined) ?? NO_PAGES;
}

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
