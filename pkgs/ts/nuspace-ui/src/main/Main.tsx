// Main: whichever Planes the URL names, drawn side by side as a strip of panes.
//
// One Viewer, and it never asks what kind of thing it is drawing. Each pane
// renders one Plane's Cells and roots their refs, every Cell the same way.
//
// Selection is router-owned: the URL /<id1>+<id2>+... is the cursor, left to
// right, the sidebar drives it, and the route effect here ships `planes.open`
// with the full list whenever it changes. The bare "/" lands on home, the
// Plane the host seeds, so there is always at least one pane.
//
// A single pane is the plane as it always was: the whole strip, centred, no
// borders. With a split every pane keeps at least the plane's measure, the
// strip scrolls sideways when they do not fit, and the borders between panes
// drag. We never remount a pane that stays open.
//
// With a split a tab bar runs across the top (./TabBar.tsx), one tab per
// pane, and the panes drop their own bars. Renaming from a tab or from a
// plane's title sends the sidebar's own `plane.rename`, so the server has one
// way in for a rename.
//
// A plane dragged off the rail onto a pane opens beside it
// (./useCanvasDrop.ts), and a tab dragged along the bar moves its pane.

import { EmptyState, type NodeProps, pathKey } from "@nustackdev/ui-kit";
import { Fragment, useCallback, useEffect, useRef } from "react";
import { useFocusedRoute, useRoutes } from "../core/router";
import { useTypePath } from "../core/surfaces";
import { notifyOp } from "../core/wire";
import {
	docPlaneSurface,
	shellPaneDivider,
	shellPaneResize,
	shellPanes,
	shellStrip,
	shellSurface,
} from "../design";
import { Pane } from "../pane/Pane";
import type { Ops } from "../plane/ops";
import type { Notify as SidebarNotify, Ops as SidebarOps } from "../sidebar/ops";
import { canDelete, deletePlane } from "../sidebar/remove";
import { usePlaneTree } from "../sidebar/state";
import {
	patchPlaneMeta,
	patchPlaneTitle,
	pruneViewer,
	useAbsent,
	usePlanes,
	useSnippets,
} from "./state";
import { TabBar } from "./TabBar";
import { useCanvasDrop } from "./useCanvasDrop";
import { usePaneWidths } from "./usePaneWidths";

/** Nothing is open. Unreachable while "/" lands home, kept as the honest
 *  fallback should a route ever come back empty. */
const NOTHING_OPEN = "pick a Plane";

export function Main({ path }: NodeProps) {
	const planes = usePlanes(path);
	const absent = useAbsent(path);
	const snippets = useSnippets(path);
	const routes = useRoutes();
	const focused = useFocusedRoute();
	const sidebar = useTypePath("SidebarRef");
	const tree = usePlaneTree(sidebar);
	const key = pathKey(path);
	const routesKey = routes.join("+");
	const stripRef = useRef<HTMLDivElement | null>(null);
	const { styleOf, onResizeStart, onResizeReset } = usePaneWidths(stripRef, routes);
	const { target: dropTarget, dropProps } = useCanvasDrop(routes);

	// One ref per op: the op name is the tail of the wire path, not a key in
	// the payload. `path` is this node's own address in the tree.
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const notify = useCallback(
		<K extends keyof Ops & string>(op: K, args: Ops[K]) => notifyOp<Ops, K>(path, op, args),
		[key],
	);

	// The full list, every time it changes and once on load -- an empty one
	// included, so the server stops shipping a Plane nobody has open. Planes
	// and editor state of panes that closed go at the same moment.
	// biome-ignore lint/correctness/useExhaustiveDependencies: routes is compared by its joined key; path by value.
	useEffect(() => {
		notify("planes.open", { plane_ids: routes });
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

	// Optimistic: the switch moves now, the next `set_plane` confirms it.
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const onMeta = useCallback(
		(planeId: string, meta: Record<string, unknown>) => {
			patchPlaneMeta(path, planeId, meta);
			notify("plane.meta", { plane_id: planeId, meta });
		},
		[key, notify],
	);

	// Optimistic like `onMeta`. The op is the sidebar's: it is the one that
	// already renames a Plane, and the tree it reships carries the new title.
	// biome-ignore lint/correctness/useExhaustiveDependencies: paths are compared by value.
	const onRename = useCallback(
		(planeId: string, title: string) => {
			patchPlaneTitle(path, planeId, title);
			if (sidebar) {
				notifyOp<SidebarOps, "plane.rename">(sidebar, "plane.rename", { plane_id: planeId, title });
			}
		},
		[key, sidebar ? pathKey(sidebar) : ""],
	);

	// Optimistic like `onMeta`, and through the sidebar's op like `onRename`:
	// the sidebar's is the one that sets an icon, and both the tree and the
	// plane it reships carry it.
	// biome-ignore lint/correctness/useExhaustiveDependencies: paths are compared by value.
	const onIcon = useCallback(
		(planeId: string, icon: string) => {
			patchPlaneMeta(path, planeId, { icon });
			if (sidebar) {
				notifyOp<SidebarOps, "plane.icon">(sidebar, "plane.icon", { plane_id: planeId, icon });
			}
		},
		[key, sidebar ? pathKey(sidebar) : ""],
	);

	// Through the sidebar's op and its confirm, like `onRename`: a delete from
	// a pane's `...` is the sidebar's delete. Undefined for a system Plane.
	const deleteOf = (planeId: string): (() => void) | undefined => {
		if (!sidebar || !canDelete(tree, planeId)) return undefined;
		const notifySidebar: SidebarNotify = (op, args) =>
			notifyOp<SidebarOps, typeof op>(sidebar, op, args);
		const title = planes[planeId]?.title || tree[planeId]?.title || planeId;
		return () => void deletePlane(notifySidebar, tree, planeId, title);
	};

	if (routes.length === 0) {
		return (
			<div className={shellSurface}>
				<div className={docPlaneSurface}>
					<EmptyState>{NOTHING_OPEN}</EmptyState>
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
					planes={planes}
					absent={absent}
					focused={focused}
					stripRef={stripRef}
					onMeta={onMeta}
					onRename={onRename}
					deleteOf={deleteOf}
				/>
			) : null}
			<div ref={stripRef} className={shellPanes} {...dropProps}>
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
							planeId={id}
							plane={planes[id] ?? null}
							absent={absent[id] ?? null}
							snippets={snippets}
							notify={notify}
							onMeta={onMeta}
							onRename={onRename}
							onIcon={onIcon}
							onDelete={deleteOf(id)}
							split={split}
							divided={i > 0}
							focused={id === focused}
							drop={dropTarget?.id === id ? dropTarget.edge : null}
							style={styleOf(i)}
						/>
					</Fragment>
				))}
			</div>
		</div>
	);
}
