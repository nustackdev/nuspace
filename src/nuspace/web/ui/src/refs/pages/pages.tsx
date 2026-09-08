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
import { useStore } from "@nustackdev/ui-kit";
import { useCallback, useEffect, useMemo } from "react";
import { docPage } from "../../design";
import { useRoute } from "../../router";
import { Canvas } from "./Canvas";
import { Rail } from "./Rail";
import {
	pagesSliceFactory,
	patchEditor,
	useEditorState,
	usePagesValue,
} from "./slice";
import { EMPTY_TREE } from "./types";

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

	return (
		<div className="flex min-h-0 min-w-0 flex-1">
			<Rail
				tree={tree}
				expanded={expanded}
				onToggle={toggleExpanded}
				selectedPath={route.path}
				notify={notify}
			/>
			<div className={`${docPage} flex min-w-0 flex-1 flex-col`}>
				{page == null ? (
					<div className="p-8 font-mono text-sm text-text-muted">
						loading page...
					</div>
				) : (
					<>
						<header className="mx-auto w-full max-w-doc px-doc-pad-x pt-16">
							<button
								type="button"
								onClick={() => {
									if (page.path.length === 0) return;
									const title = window.prompt("rename page", page.title);
									if (title)
										notify({ op: "on_page_rename", path: page.path, title });
								}}
								className="w-full truncate text-left text-3xl font-semibold tracking-tight text-text-primary"
							>
								{page.title || (page.path.length === 0 ? "Space" : "Untitled")}
							</button>
						</header>
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
