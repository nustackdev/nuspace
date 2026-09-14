// PagesRef -- the nuspace document editor.
//
// Two columns: the page rail on the left, one page's block canvas on the
// right. Blocks never appear in the rail; they are parts of a page, not
// navigable entities.
//
// The node owns everything runtime (see `state.ts`). Selection is
// router-owned: the URL /pages/<page_id> is the cursor, so a click drives
// navigate() and the route effect ships `page.select`. Pages are flat, so the
// route is one id however deep the page sits; /pages with no segment is the
// root page, which is a real page and may carry blocks.
//
// We never remount the shell on navigation.

import { type NodeEntry, type NodeProps, pathKey, Spinner } from "@nustackdev/ui-kit";
import { useCallback, useEffect, useMemo, useState } from "react";
import { hrefFor, onNavClick, useRoute } from "../../app/router";
import { notifyOp } from "../../app/wire";
import type { Crumb } from "../../components";
import { PageHeader } from "../../components";
import { docPageLoading, docPageSurface, shellSurface } from "../../design";
import { Canvas } from "./Canvas";
import type { Ops } from "./ops";
import { Rail } from "./Rail";
import { applyPagesWrite, patchEditor, useEditorState, usePagesValue, useStarters } from "./state";
import { ancestorsOf, type PageTree, rootId } from "./types";

// Empty-state labels. The root page ships an empty title (the server inits it
// that way), so something has to stand in for it; "Space" is what the rail
// already calls it, and the header disagreeing with the rail about the name of
// the same page is the odd part of the old empty state, not the word itself.
// Both are placeholders now - muted, and typing over one names the page - so
// neither can be mistaken for a title that is really there.
const SPACE_FALLBACK = "Space";
const PAGE_FALLBACK = "Untitled";

/**
 * The trail to a page: every ancestor, the space included, the page itself
 * excluded. The big title right below is the current page; repeating it in
 * the crumb reads as a stutter, and the crumb is there to say what is ABOVE
 * you.
 *
 * Walked off `parent` links rather than off a path, because a page carries no
 * path: it is one row at a fixed depth and the tree is the relation between
 * rows.
 */
function trailFor(tree: PageTree, pageId: string): Crumb[] {
	const root = rootId(tree);
	// The root page IS the space. A trail reading "Space > Space" is noise.
	if (!pageId || pageId === root) return [];
	return ancestorsOf(tree, pageId).map((row) => ({
		label: row.title || (row.id === root ? SPACE_FALLBACK : PAGE_FALLBACK),
		href: hrefFor("pages", row.id === root ? [] : [row.id]),
		onClick: onNavClick({ top: "pages", path: row.id === root ? [] : [row.id] }),
	}));
}

function PagesView({ path }: NodeProps) {
	const { tree, page, loaded } = usePagesValue(path);
	const editor = useEditorState(path);
	const starters = useStarters(path);
	const route = useRoute();
	const key = pathKey(path);

	const expanded = useMemo(() => new Set(editor.expanded), [editor.expanded]);

	// One ref per op: the op name is the tail of the wire path, not a key in
	// the payload. `path` is this node's own address in the tree.
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const notify = useCallback(
		<K extends keyof Ops & string>(op: K, args: Ops[K]) => notifyOp<Ops, K>(path, op, args),
		[key],
	);

	// The router path under /pages is at most one page id; empty is the root
	// page, whose id the tree tells us (it is the row that parents itself).
	const selected = route.path[0] ?? rootId(tree);
	useEffect(() => {
		if (route.top !== "pages" || !selected) return;
		notify("page.select", { page_id: selected });
	}, [selected, route.top, notify]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const toggleExpanded = useCallback(
		(key: string) => {
			patchEditor(path, (e) => {
				const next = new Set(e.expanded);
				if (next.has(key)) next.delete(key);
				else next.add(key);
				return { expanded: Array.from(next) };
			});
		},
		[key],
	);

	// The rename round trip is a kv write, a substrate notification and a
	// reship, so `page.title` lags the keystroke by a frame or two. Hold the
	// committed title locally until the server's copy agrees, otherwise the
	// heading you just typed snaps back. Keyed by page path so it cannot leak
	// onto the next page you open.
	const [pending, setPending] = useState<{ key: string; title: string } | null>(null);
	const pageKey = page ? page.page_id : "";
	const renamed =
		pending && pending.key === pageKey && pending.title !== page?.title ? pending.title : null;

	const rename = useCallback(
		(title: string) => {
			if (!page) return;
			setPending({ key: page.page_id, title });
			notify("page.rename", { page_id: page.page_id, title });
		},
		[notify, page],
	);

	return (
		<div className={shellSurface}>
			<Rail
				tree={tree}
				loaded={loaded}
				expanded={expanded}
				onToggle={toggleExpanded}
				selectedId={selected}
				notify={notify}
			/>
			<div className={docPageSurface}>
				{page == null ? (
					<div className={docPageLoading}>
						<Spinner size="sm" tone="neutral" label="Loading page" />
						loading page...
					</div>
				) : (
					<>
						<PageHeader
							title={renamed ?? page.title}
							seed={page.page_id}
							crumbs={trailFor(tree, page.page_id)}
							placeholder={page.page_id === rootId(tree) ? SPACE_FALLBACK : PAGE_FALLBACK}
							onRename={rename}
						/>
						<Canvas refPath={path} page={page} starters={starters} notify={notify} />
					</>
				)}
			</div>
		</div>
	);
}

export const PagesRef: NodeEntry = {
	component: PagesView,
	handlers: { write: (ctx, payload) => ctx.update((props) => applyPagesWrite(props, payload)) },
};
