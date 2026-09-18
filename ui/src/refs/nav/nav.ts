// NuspaceNavRef -- the browser answering "where am I?".
//
// Mirrors `nuspace/web/refs/nav.py`. The route is per view, so the browser
// owns it outright and the server keeps no copy: an arm that needs to know
// which page this connection is looking at sends a `read` frame, and this
// answers it off the live URL.
//
// Pulled, never pushed. There is no `write` handler, so a server that tried
// to move somebody's tab gets the store's "op not supported" rather than a
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
// The root page's id is not hardcoded here. It is found on whichever node in
// the tree is a PagesRef -- the root is the one row that parents itself -- so
// this file knows nothing about what the store calls it.
//
// `read` is the one handler, and it earns its place: the default answers with
// `props.value`, and this ref has no stored value to answer with. A mirrored
// route is a stale route the moment somebody uses the back button.

import { OPS, type TreeNode } from "@nustackdev/ui-core";
import { type NodeEntry, tree } from "@nustackdev/ui-kit";
import { type PageTree, rootId } from "../pages/types";

export type Route = { top: string; page_id: string };

/** The URL, split. Read directly: the read path is not inside a render. */
function currentRoute(): { top: string; path: string[] } {
	const parts = window.location.pathname.split("/").filter((s) => s.length > 0);
	return { top: parts[0] ?? "pages", path: parts.slice(1).map(decodeURIComponent) };
}

function findPages(node: TreeNode): PageTree | null {
	for (const child of node.children.values()) {
		if (child.type === "PagesRef") return (child.props.tree as PageTree | undefined) ?? null;
		const deeper = findPages(child);
		if (deeper) return deeper;
	}
	return null;
}

/** The root page's id, off whichever node is holding the page tree. */
function rootPageId(): string {
	const pages = findPages(tree.getState().root);
	return pages ? rootId(pages) : "";
}

/** The page id the URL names, or the root page's when it names none. */
export function routePageId(path: string[]): string {
	return path[0] || rootPageId();
}

/** Structural: bound to the URL, renders nothing into the visible tree. */
function NavView() {
	return null;
}

export const NuspaceNavRef: NodeEntry = {
	component: NavView,
	handlers: {
		read: (ctx) => {
			const { top, path } = currentRoute();
			ctx.send(OPS.read, { top, page_id: routePageId(path) } satisfies Route, ctx.frame.id);
		},
	},
};
