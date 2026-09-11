// PagesRef -- the nuspace document editor.
//
// Two columns: the page rail on the left, one page's block canvas on the
// right. Blocks never appear in the rail; they are parts of a page, not
// navigable entities.
//
// The slice owns everything runtime (see `slice.ts`). Selection is
// router-owned: the URL /pages/<pid>/<pid> is the cursor, so a click drives
// navigate() and the route effect ships `on_page_select`. /pages with no
// segments is the root page, which is a real page and may carry blocks.
//
// We never remount the shell on navigation. The mvp did, and it wipes every
// slice on the page.

import { OP_NOTIFY } from "@nustackdev/ui-core";
import type { RefEntry } from "@nustackdev/ui-kit";
import { Spinner, useStore } from "@nustackdev/ui-kit";
import { useCallback, useEffect, useMemo, useState } from "react";
import { hrefFor, onNavClick, useRoute } from "../../app/router";
import type { Crumb } from "../../components";
import { PageHeader } from "../../components";
import { docPageLoading, docPageSurface, shellSurface } from "../../design";
import { Canvas } from "./Canvas";
import { Rail } from "./Rail";
import { pagesSliceFactory, patchEditor, useEditorState, usePagesValue } from "./slice";
import { EMPTY_TREE, type PageNode } from "./types";

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
 * Titles come off the tree rather than off the page, because the path is a
 * list of ids and only the tree knows what they are called.
 */
function trailFor(tree: PageNode, path: string[]): Crumb[] {
	// The root page IS the space. A trail reading "Space > Space" is noise.
	if (path.length === 0) return [];
	const out: Crumb[] = [];
	let node: PageNode | undefined = tree;
	const prefix: string[] = [];
	out.push({
		label: tree.title || SPACE_FALLBACK,
		href: hrefFor("pages", []),
		onClick: onNavClick({ top: "pages", path: [] }),
	});
	// Ancestors only: stop one short of the page we are looking at.
	for (const pid of path.slice(0, -1)) {
		node = node?.pages.find((p) => p.id === pid);
		if (!node) break;
		prefix.push(pid);
		const at = [...prefix];
		out.push({
			label: node.title || PAGE_FALLBACK,
			href: hrefFor("pages", at),
			onClick: onNavClick({ top: "pages", path: at }),
		});
	}
	return out;
}

function PagesView({ path }: { path: string }) {
	const value = usePagesValue(path);
	const editor = useEditorState(path);
	const send = useStore((s) => s.send);
	const route = useRoute();

	const tree = value?.tree ?? EMPTY_TREE;
	const page = value?.page ?? null;
	const expanded = useMemo(() => new Set(editor.expanded), [editor.expanded]);

	const notify = useCallback(
		(payload: Record<string, unknown>) => {
			send({ op: OP_NOTIFY, ref: path, payload });
		},
		[path, send],
	);

	// The router path under /pages is [pid...]; empty is the root page.
	const selectionKey = route.path.join("/");
	// biome-ignore lint/correctness/useExhaustiveDependencies: selectionKey captures route.path's content; route.path itself is a fresh array each render
	useEffect(() => {
		if (route.top !== "pages") return;
		send({
			op: OP_NOTIFY,
			ref: path,
			payload: { op: "on_page_select", path: route.path },
		});
	}, [selectionKey, route.top, path, send]);

	const toggleExpanded = useCallback(
		(key: string) => {
			patchEditor(path, (e) => {
				const next = new Set(e.expanded);
				if (next.has(key)) next.delete(key);
				else next.add(key);
				return { expanded: Array.from(next) };
			});
		},
		[path],
	);

	// Renaming ships `on_page_rename` and the server reships the TREE, not the
	// open page, so `page.title` keeps the old value until you navigate away
	// and back. Hold the committed title locally until the server's copy
	// agrees, otherwise the heading you just typed snaps back one frame later.
	// Keyed by page path so it cannot leak onto the next page you open.
	const [pending, setPending] = useState<{ key: string; title: string } | null>(null);
	const pageKey = page ? page.path.join("/") : "";
	const renamed =
		pending && pending.key === pageKey && pending.title !== page?.title ? pending.title : null;

	const rename = useCallback(
		(title: string) => {
			if (!page) return;
			const at = page.path;
			setPending({ key: at.join("/"), title });
			notify({ op: "on_page_rename", path: at, title });
		},
		[notify, page],
	);

	return (
		<div className={shellSurface}>
			<Rail
				tree={tree}
				expanded={expanded}
				onToggle={toggleExpanded}
				selectedPath={route.path}
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
							seed={page.page_id ?? ""}
							crumbs={trailFor(tree, page.path)}
							placeholder={page.path.length === 0 ? SPACE_FALLBACK : PAGE_FALLBACK}
							onRename={rename}
						/>
						<Canvas refPath={path} page={page} notify={notify} />
					</>
				)}
			</div>
		</div>
	);
}

export const PagesRef: RefEntry = {
	factory: pagesSliceFactory,
	component: PagesView,
};
