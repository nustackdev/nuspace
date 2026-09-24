// The sidebar rail: a fixed header, a section per group, a fixed footer.
//
// Planes only. Cells are parts of a Plane, not navigable entities, so they
// never appear here.
//
// Selection is router-owned: the URL /<id1>+<id2>+... is the cursor, one id
// per pane, and the Viewer ships `pages.open` off the route. A plain row click
// replaces the focused pane (or opens the first), cmd/ctrl-click or the row's
// split button appends a pane. Every open Plane's row is washed, the focused
// pane's strongest. The rail itself holds no selection state.
//
// ## Sections
//
// Two of the three kinds of row are shims the server invents: one for the
// Space, which is the tree's root and is never drawn because the header strip
// is what a person sees in its place, and one per group, which is a section.
// What a section is called and which Planes are in it are both the server's
// answer, so adding a group adds a section and nothing here changes.
//
// A section is an ordinary row with an ordinary twisty, which is what keeps the
// flatten, the fold state and the roving focus working one level deeper
// without knowing a section exists. What it is not is a place: it has no Plane
// behind it, so it never navigates, and opening it is the only thing it does.
//
// ## Where the parts are
//
//   Rail.tsx          this: the aside, its three strips, the resize edge
//   RailTree.tsx      the tree: keyboard, guides, the create row
//   PlaneRow.tsx      one row: twisty, label, actions, menus
//   RailRow.tsx       the row shell the three lanes sit in
//   tree.ts           flatten, and the row shape it produces
//   useReveal.ts      revealed-then-sticky expansion
//   useDraft.ts       inline rename + create
//   useRailFocus.ts   the one tab stop
//   useRailWidth.ts   the drag-resized width
//
// Every class string and the geometry are in design/rail.ts.

import { Skeleton } from "@nustackdev/ui-kit";
import { useMemo } from "react";
import { useFocusedRoute, useRoutes } from "../app/router";
import {
	railAside,
	railIndent,
	railResizeHandle,
	railScroll,
	railSkeletonBar,
	railSkeletonRow,
} from "../design";
import type { Notify } from "./ops";
import { RailFooter } from "./RailFooter";
import { RailHeader } from "./RailHeader";
import { RailTree } from "./RailTree";
import { visibleRows } from "./tree";
import { childrenOf, type PageTree, rootId } from "./types";
import { useRailWidth } from "./useRailWidth";
import { useReveal } from "./useReveal";

const RAIL_LABEL = "nuspace";

export function Rail({
	tree,
	loaded,
	expanded,
	onToggle,
	notify,
}: {
	tree: PageTree;
	loaded: boolean;
	expanded: Set<string>;
	onToggle: (key: string) => void;
	notify: Notify;
}) {
	const routes = useRoutes();
	// A bare "/" has nothing open, and no row stands in for that: the row that
	// stands for the Space is the tree's root and is not drawn. The focused
	// pane's Plane is the cursor; the others are merely open.
	const selKey = useFocusedRoute();
	const { width, onResizeStart, onResizeReset } = useRailWidth();
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
		<aside className={railAside} style={{ width }}>
			<RailHeader label={RAIL_LABEL} />
			<nav aria-label="Planes" className={railScroll}>
				{loading ? (
					<RailSkeleton />
				) : (
					<RailTree
						tree={tree}
						rows={rows}
						routes={routes}
						selKey={selKey}
						onToggle={onToggle}
						reveal={reveal}
						notify={notify}
					/>
				)}
			</nav>
			<RailFooter />
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
