// The sidebar rail: a header group (top bar, search, the pinned planes), a
// body (the scrolling tree, its sticky New plane row first), a bottom bar.
//
// Planes only. Cells are parts of a Plane, not navigable entities, so they
// never appear here.
//
// Selection is router-owned (../core/router.ts): the History entry holds the
// panes and the URL is the focused one, and the Viewer ships `planes.open` off
// it. A row is a real link, so the shell's anchor catcher takes its click: plain
// replaces the focused pane (or opens the first), Option opens it beside,
// cmd/ctrl-click opens it in a browser tab, and the row's split item or a drag
// onto the panes adds a pane.
// Every open Plane's row is washed, the focused pane's strongest. The rail
// itself holds no selection state.
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
//   Rail.tsx          this: the aside and its strips
//   RailHeader.tsx    the top bar: collapse, the wordmark
//   NewPlaneRow.tsx   the tree's sticky first row, which makes a top-level plane
//   SearchTrigger.tsx the search entry under it, opening the search Plane
//   PinnedRow.tsx     the pinned planes, the header group's last strip
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
//   collapse.ts       folded or not, and cmd/ctrl+\
//
// Every class string and the geometry are in design/rail.ts. The width and
// the fold are the shell's split panel the rail sits in (../shell/Shell.tsx).

import { Skeleton } from "@nustackdev/ui-kit";
import { useMemo } from "react";
import { useSkeleton } from "../core/delay";
import { useFocusedRoute, useRoutes } from "../core/router";
import {
	railAside,
	railIndent,
	railPinShelf,
	railScroll,
	railSkeletonBar,
	railSkeletonRow,
} from "../design";
import { AddPlane } from "./AddPlane";
import { NewPlaneRow } from "./NewPlaneRow";
import type { Notify } from "./ops";
import { PinnedRow } from "./PinnedRow";
import type { Pins } from "./pin";
import { RailFooter } from "./RailFooter";
import { RailHeader } from "./RailHeader";
import { RailTree } from "./RailTree";
import { SearchTrigger } from "./SearchTrigger";
import { useSearchShortcut } from "./search";
import { visibleRows } from "./tree";
import { childrenOf, type PlaneTree, type Registered, rootId } from "./types";
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
	const root = rootId(tree);
	// The tree lands in one `set_tree`; until it does there is nothing to draw
	// and the honest thing is row-shaped placeholders, not a fake empty tree.
	const loading = !loaded || !root;

	const rows = useMemo(
		() => visibleRows(tree, childrenOf(tree, rootId(tree)), expanded),
		[tree, expanded],
	);

	const reveal = useReveal({ tree, root, routes, selKey, expanded, onToggle });
	useSearchShortcut();

	return (
		// Folded is inert, not unmounted: the Add plane popup lives here and a
		// pane's `...` still opens it, and cmd/ctrl+K still opens search.
		<aside aria-label="Sidebar" className={railAside}>
			<RailHeader />
			<SearchTrigger />
			{loading ? null : (
				<PinnedRow
					tree={tree}
					pins={pins}
					registered={registered}
					routes={routes}
					selKey={selKey}
					reveal={reveal}
					className={railPinShelf}
				/>
			)}
			<nav aria-label="Planes" className={railScroll}>
				{loading ? null : <NewPlaneRow />}
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
		</aside>
	);
}

/**
 * The rail before its node is on the tree, at boot: the aside, its two bars
 * and skeleton rows, at the width the real one will take. The rows hold off
 * like the viewer skeleton does, so a fast boot never flashes them.
 */
export function RailPlaceholder() {
	const shown = useSkeleton();
	return (
		<aside aria-label="Sidebar" className={railAside}>
			<RailHeader />
			<nav aria-label="Planes" className={railScroll}>
				{shown ? <RailSkeleton /> : null}
			</nav>
			<RailFooter />
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
