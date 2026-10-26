// The sidebar rail: a top bar, the one thing fixed up there, a body that
// scrolls (the nav rows, then the pinned, the planes and the extensions,
// each under a section header), a bottom bar.
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
// drag and drop. Home, search and settings are the nav rows (./nav.ts), so
// the tree skips them.
//
// ## Where the parts are
//
//   Rail.tsx          this: the aside and its strips
//   RailHeader.tsx    the top bar: collapse, the wordmark
//   NavRows.tsx       home, search and settings, the body's first rows; ./nav.ts for their keys
//   RailSection.tsx   a section header in the body, and its action
//   NewPlaneRow.tsx   the tree's first row, which makes a top-level plane
//   Pinned.tsx        the pinned planes, under the nav rows
//   Extensions.tsx    what each extension offers, folded by package; a click makes one
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
import { railAside, railIndent, railScroll, railSkeletonBar, railSkeletonRow } from "../design";
import { AddPlane } from "./AddPlane";
import { Extensions, extensionGroups, extensionLines } from "./Extensions";
import { NAV_ITEMS, NavRows } from "./NavRows";
import { NewPlaneRow } from "./NewPlaneRow";
import { NAV_PLANES, useSettingsShortcut } from "./nav";
import type { Notify } from "./ops";
import { Pinned, shownPins } from "./Pinned";
import type { Pins } from "./pin";
import { RailFooter } from "./RailFooter";
import { RailHeader } from "./RailHeader";
import { RailSection } from "./RailSection";
import { RailTree } from "./RailTree";
import { useSearchShortcut } from "./search";
import { visibleRows } from "./tree";
import { childrenOf, type PlaneTree, type Registered, rootId } from "./types";
import { NEW_PLANE_KEY, navKey, pinKey, RailFocusContext, useRailFocus } from "./useRailFocus";
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
		() => visibleRows(tree, childrenOf(tree, rootId(tree)), expanded, NAV_PLANES),
		[tree, expanded],
	);

	const reveal = useReveal({ tree, root, routes, selKey, expanded, onToggle });

	const groups = useMemo(() => extensionGroups(registered), [registered]);
	const lines = useMemo(() => extensionLines(groups, expanded), [groups, expanded]);
	const pinned = useMemo(() => shownPins(tree, pins.ids), [tree, pins.ids]);

	// Every row of the body, in the order it is drawn: what the arrows walk.
	const keys = useMemo(
		() =>
			loading
				? NAV_KEYS
				: [
						...NAV_KEYS,
						...pinned.map(pinKey),
						NEW_PLANE_KEY,
						...rows.map((r) => r.key),
						...lines.map((l) => l.key),
					],
		[loading, pinned, rows, lines],
	);
	// The tab stop falls back to the open plane's row: its nav row, its tree
	// row, or its pin.
	const selRow = NAV_PLANES.has(selKey)
		? navKey(selKey)
		: rows.some((r) => r.key === selKey)
			? selKey
			: pinned.includes(selKey)
				? pinKey(selKey)
				: null;
	const focus = useRailFocus(keys, selRow);
	useSearchShortcut();
	useSettingsShortcut();

	return (
		// Folded is inert, not unmounted: the Add plane popup lives here and a
		// pane's `...` still opens it, and cmd/ctrl+K and cmd/ctrl+comma still
		// open search and settings.
		<aside aria-label="Sidebar" className={railAside}>
			<RailHeader />
			<RailFocusContext value={focus}>
				{/* The body takes the focus a click leaves, out of the tab order: see ./useRailFocus.ts. */}
				<nav
					aria-label="Planes"
					ref={focus.containerRef}
					className={railScroll}
					tabIndex={-1}
					onClick={focus.onClick}
					onKeyDown={focus.onKeyDown}
				>
					<NavRows routes={routes} selKey={selKey} />
					{loading ? (
						<RailSkeleton />
					) : (
						<>
							<Pinned
								tree={tree}
								pins={pins}
								routes={routes}
								selKey={selKey}
								reveal={reveal}
								notify={notify}
							/>
							<RailSection label="Planes" />
							<NewPlaneRow />
							<RailTree
								tree={tree}
								rows={rows}
								routes={routes}
								selKey={selKey}
								onToggle={onToggle}
								reveal={reveal}
								notify={notify}
								pins={pins}
							/>
							<Extensions
								groups={groups}
								lines={lines}
								expanded={expanded}
								onToggle={onToggle}
								notify={notify}
							/>
						</>
					)}
				</nav>
			</RailFocusContext>
			<RailFooter />
			<AddPlane registered={registered} notify={notify} reveal={reveal} />
		</aside>
	);
}

/**
 * The rail before its node is on the tree, at boot: the aside, its two bars,
 * the nav rows and skeleton rows, at the width the real one will take. The rows hold off
 * like the viewer skeleton does, so a fast boot never flashes them.
 */
export function RailPlaceholder() {
	const shown = useSkeleton();
	const routes = useRoutes();
	const selKey = useFocusedRoute();
	const focus = useRailFocus(NAV_KEYS, NAV_PLANES.has(selKey) ? navKey(selKey) : null);
	return (
		<aside aria-label="Sidebar" className={railAside}>
			<RailHeader />
			<RailFocusContext value={focus}>
				{/* The body takes the focus a click leaves, out of the tab order: see ./useRailFocus.ts. */}
				<nav
					aria-label="Planes"
					ref={focus.containerRef}
					className={railScroll}
					tabIndex={-1}
					onClick={focus.onClick}
					onKeyDown={focus.onKeyDown}
				>
					<NavRows routes={routes} selKey={selKey} />
					{shown ? <RailSkeleton /> : null}
				</nav>
			</RailFocusContext>
			<RailFooter />
		</aside>
	);
}

/** The nav rows' keys, the body's first. */
const NAV_KEYS = NAV_ITEMS.map((item) => navKey(item.id));

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
