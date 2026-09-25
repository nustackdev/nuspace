// The sidebar rail: a top bar, the pinned planes, the tree, a bottom bar.
//
// Planes only. Cells are parts of a Plane, not navigable entities, so they
// never appear here.
//
// Selection is router-owned: the URL /<id1>+<id2>+... is the cursor, one id
// per pane, and the Viewer ships `planes.open` off the route. A plain row click
// replaces the focused pane (or opens the first), cmd/ctrl-click or the row's
// split item appends a pane. Every open Plane's row is washed, the focused
// pane's strongest. The rail itself holds no selection state.
//
// ## One tree
//
// Every Plane that draws, by parent, in sibling order. The server invents one
// row for the Space, the tree's root, which is never drawn. Grouping is
// nesting, and a Plane with no cells works as a folder. Rows move freely by
// drag and drop.
//
// ## Where the parts are
//
//   Rail.tsx          this: the aside, its three strips, the resize edge
//   RailHeader.tsx    the top bar: collapse, new plane
//   PinnedRow.tsx     the pinned planes, under the top bar
//   RailFooter.tsx    the bottom bar: links, connection, theme
//   pin.ts            the pins and their ops
//   RailTree.tsx      the tree: keyboard, drop marks
//   PlaneRow.tsx      one row: icon and twisty, label, actions, menus
//   RailRow.tsx       the row shell the three lanes sit in
//   AddPlane.tsx      the Add plane popup, and ./add.ts for who opened it
//   tree.ts           flatten, and the row shape it produces
//   useRailDrag.ts    drag and drop
//   useReveal.ts      revealed-then-sticky expansion
//   useDraft.ts       inline rename
//   useRailFocus.ts   the one tab stop
//   useRailWidth.ts   the drag-resized width
//   collapse.ts       hidden or not, and cmd/ctrl+\
//
// Every class string and the geometry are in design/rail.ts.

import { Skeleton } from "@nustackdev/ui-kit";
import { useMemo } from "react";
import { useFocusedRoute, useRoutes } from "../core/router";
import {
	railAside,
	railIndent,
	railResizeHandle,
	railScroll,
	railSkeletonBar,
	railSkeletonRow,
} from "../design";
import { AddPlane } from "./AddPlane";
import { useRailCollapsed } from "./collapse";
import type { Notify } from "./ops";
import { PinnedRow } from "./PinnedRow";
import type { Pins } from "./pin";
import { RailFooter } from "./RailFooter";
import { RailHeader } from "./RailHeader";
import { RailTree } from "./RailTree";
import { visibleRows } from "./tree";
import { childrenOf, type PlaneTree, type Registered, rootId } from "./types";
import { useRailWidth } from "./useRailWidth";
import { useReveal } from "./useReveal";

export function Rail({
	tree,
	loaded,
	registered,
	expanded,
	onToggle,
	notify,
	pins,
}: {
	tree: PlaneTree;
	loaded: boolean;
	registered: Registered[];
	expanded: Set<string>;
	onToggle: (key: string) => void;
	notify: Notify;
	pins: Pins;
}) {
	const routes = useRoutes();
	// The focused pane's Plane is the cursor; the others are merely open.
	const selKey = useFocusedRoute();
	const { width, onResizeStart, onResizeReset } = useRailWidth();
	const collapsed = useRailCollapsed();
	const root = rootId(tree);
	// The tree lands in one `set_tree`; until it does there is nothing to draw
	// and the honest thing is row-shaped placeholders, not a fake empty tree.
	const loading = !loaded || !root;

	const rows = useMemo(
		() => visibleRows(tree, childrenOf(tree, rootId(tree)), expanded),
		[tree, expanded],
	);

	const reveal = useReveal({ tree, root, routes, selKey, expanded, onToggle });

	return (
		// Collapsed is hidden, not unmounted: the Add plane popup lives here and
		// a pane's `...` still opens it.
		<aside aria-label="Sidebar" className={railAside(collapsed)} style={{ width }}>
			<RailHeader />
			{loading ? null : (
				<PinnedRow
					tree={tree}
					pins={pins}
					registered={registered}
					routes={routes}
					selKey={selKey}
					reveal={reveal}
				/>
			)}
			<nav aria-label="Planes" className={railScroll}>
				{loading ? (
					<RailSkeleton />
				) : (
					<RailTree
						tree={tree}
						rows={rows}
						registered={registered}
						routes={routes}
						selKey={selKey}
						onToggle={onToggle}
						reveal={reveal}
						notify={notify}
						pins={pins}
					/>
				)}
			</nav>
			<RailFooter />
			<AddPlane registered={registered} notify={notify} reveal={reveal} />
			<div
				aria-hidden="true"
				className={railResizeHandle}
				onPointerDown={onResizeStart}
				onDoubleClick={onResizeReset}
			/>
		</aside>
	);
}

/** Row-shaped placeholders, so the rail does not resize when the list lands. */
function RailSkeleton() {
	return (
		<div aria-busy="true">
			{[0, 1, 1].map((depth, i) => (
				<div
					// biome-ignore lint/suspicious/noArrayIndexKey: placeholders have no identity
					key={i}
					className={railSkeletonRow()}
					style={railIndent(depth)}
				>
					<Skeleton className={railSkeletonBar} />
				</div>
			))}
		</div>
	);
}
