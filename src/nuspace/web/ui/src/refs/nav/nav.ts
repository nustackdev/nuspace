// NuspaceNavRef -- the browser answering "where am I?".
//
// Mirrors `nuspace/web/refs/nav.py`. The route is per view, so the browser
// owns it outright and the server keeps no copy: an arm that needs to know
// which page this connection is looking at sends a `read` frame, and the
// kit's store answers it out of this slice's `get()`.
//
// Pulled, never pushed. There is no `write` on the slice, so a server that
// tried to move somebody's tab would get an `op_not_allowed` rather than a
// silent navigation; and there is no notify on navigation either, because
// every arm that cares reads the route when it runs. `page.select` is what
// tells the server a tab moved, and it is a PagesRef op, not a nav one.
//
// The shape is `{top, page_id}`:
//
//   top      which surface is showing -- "pages", "apps", "lens".
//   page_id  the page under /pages. Bare /pages is the space's root page,
//            which is a real page and may carry blocks, so its id is what
//            goes on the wire rather than an empty string: an empty kv key
//            segment is not a key, so the server could not address it.
//
// The root page's id is not hardcoded here. It is found on the pages slice's
// tree -- the root is the one row that parents itself -- so this file knows
// nothing about what the store calls it.

import type { RefEntry, RefSlice, SliceFactory } from "@nustackdev/ui-kit";
import { useStore } from "@nustackdev/ui-kit";
import { type PageTree, rootId } from "../pages/types";

export type Route = { top: string; page_id: string };

type NavSlice = RefSlice & { value: Route; get: () => Route };

/** The URL, split. Read directly: the read path is not inside a render. */
function currentRoute(): { top: string; path: string[] } {
	const parts = window.location.pathname.split("/").filter((s) => s.length > 0);
	return { top: parts[0] ?? "pages", path: parts.slice(1).map(decodeURIComponent) };
}

/** The root page's id, off whichever PagesRef slice is holding the tree. */
function rootPageId(): string {
	const { refs } = useStore.getState();
	for (const key in refs) {
		if (refs[key].type !== "PagesRef") continue;
		const value = refs[key].value as { tree?: PageTree } | undefined;
		if (value?.tree) return rootId(value.tree);
	}
	return "";
}

/** The page id the URL names, or the root page's when it names none. */
export function routePageId(path: string[]): string {
	return path[0] || rootPageId();
}

export const navSliceFactory: SliceFactory = (_path, _ctx, _props) =>
	({
		type: "NuspaceNavRef",
		value: { top: "pages", page_id: "" } as Route,
		// Answers with the live URL, not with whatever was last stored: the
		// browser is the only copy of this and a stale one is a wrong one.
		get: () => {
			const { top, path } = currentRoute();
			return { top, page_id: routePageId(path) };
		},
	}) as NavSlice;

/** Structural: bound to the URL, never rendered into the visible tree. */
function NavView(_props: { path: string }) {
	return null;
}

export const NavRef: RefEntry = {
	factory: navSliceFactory,
	component: NavView,
};
