// Main: whichever Planes the URL names, drawn side by side as a strip of panes.
//
// One Viewer, and it never asks what kind of thing it is drawing. Each pane
// renders one Plane's Cells and roots their refs, every Cell the same way.
//
// Selection is router-owned: the URL /<id1>+<id2>+... is the cursor, left to
// right, the sidebar drives it, and the route effect here ships `pages.open`
// with the full list whenever it changes. The bare "/" is home, the Plane the
// host seeds, so there is always at least one pane.
//
// A single pane is the page as it always was: the whole strip, centred, no
// borders. With a split every pane keeps at least the page's measure, the
// strip scrolls sideways when they do not fit, and the borders between panes
// drag. We never remount a pane that stays open.
//
// With a split a tab bar runs across the top (./TabBar.tsx), one tab per
// pane, and the panes drop their own bars. Renaming from a tab sends the
// sidebar's own `page.rename`, so the server has one way in for a rename.

import { type NodeProps, pathKey } from "@nustackdev/ui-kit";
import { Fragment, useCallback, useEffect, useRef } from "react";
import { useFocusedRoute, useRoutes } from "../app/router";
import { useTypePath } from "../app/surfaces";
import { notifyOp } from "../app/wire";
import {
	docPageLoading,
	docPageSurface,
	shellPaneDivider,
	shellPaneResize,
	shellPanes,
	shellStrip,
	shellSurface,
} from "../design";
import type { Ops } from "../page/ops";
import { Pane } from "../pane/Pane";
import type { Ops as SidebarOps } from "../sidebar/ops";
import { patchPageMeta, patchPageTitle, pruneViewer, usePages, useSnippets } from "./state";
import { TabBar } from "./TabBar";
import { usePaneWidths } from "./usePaneWidths";

/** Nothing is open. Unreachable while "/" routes home, kept as the honest
 *  fallback should a route ever come back empty. */
const NOTHING_OPEN = "pick a Plane";

export function Main({ path }: NodeProps) {
	const pages = usePages(path);
	const snippets = useSnippets(path);
	const routes = useRoutes();
	const focused = useFocusedRoute();
	const sidebar = useTypePath("SidebarRef");
	const key = pathKey(path);
	const routesKey = routes.join("+");
	const stripRef = useRef<HTMLDivElement | null>(null);
	const { styleOf, onResizeStart, onResizeReset } = usePaneWidths(stripRef, routes);

	// One ref per op: the op name is the tail of the wire path, not a key in
	// the payload. `path` is this node's own address in the tree.
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const notify = useCallback(
		<K extends keyof Ops & string>(op: K, args: Ops[K]) => notifyOp<Ops, K>(path, op, args),
		[key],
	);

	// The full list, every time it changes and once on load -- an empty one
	// included, so the server stops shipping a Plane nobody has open. Pages
	// and editor state of panes that closed go at the same moment.
	// biome-ignore lint/correctness/useExhaustiveDependencies: routes is compared by its joined key; path by value.
	useEffect(() => {
		notify("pages.open", { page_ids: routes });
		pruneViewer(path, routes);
	}, [routesKey, notify]);

	// A pane that just opened may be off the edge of a scrolled strip: bring
	// the focused one into view whenever the set of panes changes.
	// biome-ignore lint/correctness/useExhaustiveDependencies: runs on the pane set, not on every focus move.
	useEffect(() => {
		if (routes.length < 2 || !focused) return;
		stripRef.current
			?.querySelector<HTMLElement>(`:scope > [data-pane="${CSS.escape(focused)}"]`)
			?.scrollIntoView({ inline: "nearest", block: "nearest" });
	}, [routesKey]);

	// Optimistic: the switch moves now, the next `set_page` confirms it.
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const onMeta = useCallback(
		(pageId: string, meta: Record<string, unknown>) => {
			patchPageMeta(path, pageId, meta);
			notify("page.meta", { page_id: pageId, meta });
		},
		[key, notify],
	);

	// Optimistic like `onMeta`. The op is the sidebar's: it is the one that
	// already renames a Plane, and the tree it reships carries the new title.
	// biome-ignore lint/correctness/useExhaustiveDependencies: paths are compared by value.
	const onRename = useCallback(
		(pageId: string, title: string) => {
			patchPageTitle(path, pageId, title);
			if (sidebar) {
				notifyOp<SidebarOps, "page.rename">(sidebar, "page.rename", { page_id: pageId, title });
			}
		},
		[key, sidebar ? pathKey(sidebar) : ""],
	);

	if (routes.length === 0) {
		return (
			<div className={shellSurface}>
				<div className={docPageSurface}>
					<div className={docPageLoading}>{NOTHING_OPEN}</div>
				</div>
			</div>
		);
	}

	const split = routes.length > 1;
	// Always the same wrapper, so a pane is never remounted when the tab bar
	// comes or goes.
	return (
		<div className={shellStrip}>
			{split ? (
				<TabBar
					routes={routes}
					pages={pages}
					focused={focused}
					stripRef={stripRef}
					onMeta={onMeta}
					onRename={onRename}
				/>
			) : null}
			<div ref={stripRef} className={shellPanes}>
				{routes.map((id, i) => (
					<Fragment key={id}>
						{i > 0 ? (
							<div className={shellPaneDivider}>
								<div
									aria-hidden="true"
									className={shellPaneResize}
									onPointerDown={(e) => onResizeStart(e, i)}
									onDoubleClick={onResizeReset}
								/>
							</div>
						) : null}
						<Pane
							viewerPath={path}
							pageId={id}
							page={pages[id] ?? null}
							snippets={snippets}
							notify={notify}
							onMeta={onMeta}
							split={split}
							divided={i > 0}
							focused={id === focused}
							style={styleOf(i)}
						/>
					</Fragment>
				))}
			</div>
		</div>
	);
}
