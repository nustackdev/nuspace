// The sidebar: the whole left column. One per tab, mounted as the SidebarRef
// node (../refs/sidebar.ts).
//
// Top to bottom: the header (its `+` menu makes a plane or a desk), the nav
// section, the desk folders, the Planes tree, the Specs, the footer. The header and footer are fixed bars; the
// sections between scroll in the kit's `ScrollArea`, 10px apart, with no
// fills and no borders (design/sidebar.ts).
//
// Planes only. Cells are parts of a plane, not navigable entities, so they
// never appear here. The tree is lazy: the server ships the planes under the
// root and under every branch this tab has open, and nothing below a closed
// one. Opening a branch tells the server (`plane.expand`), which ships its
// children; closing one tells it too. Planes are flat on the wire, one row
// per plane, hierarchy in `parent` and `children`.
//
// Selection is the router's (../core/router.ts), one look for all: the row of
// what the canvas shows. On a desk item: its row in its folder (in a strip,
// the focused pane's), nothing in the nav or the Planes tree. On a solo
// plane: its nav or tree row. Folder titles never. The sidebar holds no
// selection state.
//
// Links: the rows are anchors, and the sidebar routes their plain clicks
// itself (./links.ts): a plane opens solo, a desk item opens it.
//
// ## Where the parts are
//
//   Sidebar.tsx         this: the node, the column, its placeholder at boot
//   SidebarHeader.tsx   the top bar: collapse, the wordmark, new plane
//   SidebarFooter.tsx   the bottom bar: links, shortcuts, connection, theme
//   SidebarSection.tsx  the section piece: title, count, fold, actions
//   SidebarRow.tsx      the row piece: icon, label, one trailing thing
//   ActionRow.tsx       the "New ..." row
//   NavSection.tsx      home, search, settings, through the roles (./nav.ts)
//   DeskFolders.tsx     a folder per desk: its items, strips, chips, drops; New desk
//   folders.ts          their folds, rows, selection and drop targets
//   links.ts            where a row's link goes
//   PlanesTree.tsx      the Planes tree's rows, their menus, rename, drop marks
//   Specs.tsx           the specs each package offers; a click makes one
//   AddPlane.tsx        the Add plane popup, and ./add.ts for who opened it
//   tree.ts             flatten, and the row shape it produces
//   drag.ts             drag and drop in the tree
//   useReveal.ts        revealed-then-sticky expansion
//   useDraft.ts         inline rename
//   focus.ts            the body's one tab stop
//   collapse.ts         folded or not, and cmd/ctrl+\
//
// The width and the fold are the shell's split panel the sidebar sits in
// (../shell/Shell.tsx).

import type { NodeProps } from "@nustackdev/ui-kit";
import { pathKey, ScrollArea, Skeleton } from "@nustackdev/ui-kit";
import { ChevronsDownUp } from "lucide-react";
import { useCallback, useMemo, useRef } from "react";
import { useSkeleton } from "../core/delay";
import { useRoles } from "../core/desks";
import { type Route, useFocusedRoute, useRoute, useRoutes } from "../core/router";
import { notifyOp } from "../core/wire";
import {
	sidebarAside,
	sidebarBody,
	sidebarIndent,
	sidebarScroll,
	sidebarScrollViewport,
	sidebarSkeletonBar,
	sidebarSkeletonRow,
} from "../design";
import { ActionRow } from "./ActionRow";
import { AddPlane } from "./AddPlane";
import { NEW_PLANE_KEYS, openAddPlane } from "./add";
import { DeskFolders, folderKeys, useFolders } from "./DeskFolders";
import { NEW_PLANE_KEY, navKey, SidebarFocusContext, useSidebarFocus } from "./focus";
import { selectedKey, useFolds } from "./folders";
import { useSidebarLinks } from "./links";
import { NAV_KEYS, NavSection } from "./NavSection";
import { NAV_ITEMS, rolePlanes } from "./nav";
import type { Notify, Ops } from "./ops";
import { PlanesTree } from "./PlanesTree";
import { SidebarFooter } from "./SidebarFooter";
import { SidebarHeader } from "./SidebarHeader";
import { SectionAction, SidebarSection, useSectionFold } from "./SidebarSection";
import { Specs, specGroups, specLines } from "./Specs";
import { patchSidebar, useExpanded, useSidebarValue } from "./state";
import { visibleRows } from "./tree";
import { childrenOf, ROOT_ID, rootId } from "./types";
import { useReveal } from "./useReveal";

export function Sidebar({ path }: NodeProps) {
	const { tree, loaded, registered } = useSidebarValue(path);
	const expandedList = useExpanded(path);
	const key = pathKey(path);
	const expanded = useMemo(() => new Set(expandedList), [expandedList]);
	const roles = useRoles();
	const routes = useRoutes();
	const route = useRoute();
	// The focused pane's plane, which the tree reveals.
	const focused = useFocusedRoute();
	// The selected nav or tree row: the solo plane's, none on a desk.
	const selKey = soloPlane(route);
	const root = rootId(tree);
	// The tree lands in one `set_tree`; until it does, row-shaped placeholders.
	const loading = !loaded || !root;

	// One ref per op: the op name is the tail of the wire path, not a key in
	// the payload. `path` is this node's own address in the tree.
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const notify: Notify = useCallback(
		<K extends keyof Ops & string>(op: K, args: Ops[K]) => notifyOp<Ops, K>(path, op, args),
		[key],
	);

	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const onToggle = useCallback(
		(id: string) => {
			const open = !expanded.has(id);
			patchSidebar(path, (s) => {
				const next = new Set(s.expanded);
				if (open) next.add(id);
				else next.delete(id);
				return { expanded: Array.from(next) };
			});
			notify(open ? "plane.expand" : "plane.collapse", { plane_id: id });
		},
		[key, expanded, notify],
	);

	// Collapse all: every open plane of the tree closed, the Specs groups left
	// as they are. No expand all: the tree loads a level at a time, so the
	// browser cannot tell a closed plane with children from a leaf.
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const collapseAll = useCallback(() => {
		const open = expandedList.filter((id) => Object.hasOwn(tree, id));
		if (!open.length) return;
		patchSidebar(path, (s) => ({ expanded: s.expanded.filter((id) => !open.includes(id)) }));
		for (const id of open) notify("plane.collapse", { plane_id: id });
	}, [key, expandedList, tree, notify]);

	const hidden = useMemo(() => rolePlanes(roles), [roles]);
	const rows = useMemo(
		() => visibleRows(tree, childrenOf(tree, rootId(tree)), expanded, hidden),
		[tree, expanded, hidden],
	);
	const reveal = useReveal({ tree, root, routes, selKey: focused, expanded, onToggle });
	const groups = useMemo(() => specGroups(registered), [registered]);
	const lines = useMemo(() => specLines(groups, expanded), [groups, expanded]);
	const [planesFolded, foldPlanes] = useSectionFold("planes");
	const [specsFolded, foldSpecs] = useSectionFold("specs");
	const folders = useFolders();
	const folds = useFolds();
	const aside = useRef<HTMLElement | null>(null);
	useSidebarLinks(aside);

	// Every row of the body, in the order it is drawn: what the arrows walk.
	const keys = useMemo(
		() =>
			loading
				? NAV_KEYS
				: [
						...NAV_KEYS,
						...folderKeys(folders),
						...(planesFolded ? [] : [NEW_PLANE_KEY, ...rows.map((r) => r.key)]),
						...(specsFolded ? [] : lines.map((l) => l.key)),
					],
		[loading, folders, planesFolded, rows, specsFolded, lines],
	);
	const selected = selectedRow(roles, route, rows, folds);
	const focus = useSidebarFocus(keys, selected);

	return (
		// Folded, the panel is inert, not unmounted: the Add plane popup lives
		// here and a pane's `...` still opens it.
		<aside ref={aside} aria-label="Sidebar" className={sidebarAside}>
			<SidebarHeader />
			<SidebarFocusContext value={focus}>
				{/* A click in the empty room under the sections focuses the body too, so the arrows work. */}
				<ScrollArea
					className={sidebarScroll}
					viewportClassName={sidebarScrollViewport}
					onClick={(e) => {
						const body = focus.containerRef.current;
						if (body && !body.contains(e.target as Node)) body.focus({ preventScroll: true });
					}}
				>
					{/* The body takes the focus a click leaves, out of the tab order: see ./focus.ts. */}
					<nav
						aria-label="Planes"
						ref={focus.containerRef}
						className={sidebarBody}
						tabIndex={-1}
						onClick={focus.onClick}
						onKeyDown={focus.onKeyDown}
					>
						<NavSection selKey={selKey} />
						{loading ? (
							<SidebarSkeleton />
						) : (
							<>
								<DeskFolders folders={folders} selected={selected} />
								<SidebarSection
									id="planes"
									title="Planes"
									folded={planesFolded}
									onFoldedChange={foldPlanes}
									actions={
										<SectionAction
											label="Collapse all planes"
											tip="Collapse all"
											onClick={collapseAll}
										>
											<ChevronsDownUp />
										</SectionAction>
									}
								>
									<ActionRow
										rowKey={NEW_PLANE_KEY}
										label="New plane"
										keys={NEW_PLANE_KEYS}
										onClick={() => openAddPlane({ parent: ROOT_ID })}
									/>
									<PlanesTree
										tree={tree}
										rows={rows}
										selKey={selKey}
										onToggle={onToggle}
										reveal={reveal}
										notify={notify}
									/>
								</SidebarSection>
								{groups.length ? (
									<SidebarSection
										id="specs"
										title="Specs"
										folded={specsFolded}
										onFoldedChange={foldSpecs}
									>
										<Specs
											groups={groups}
											lines={lines}
											expanded={expanded}
											onToggle={onToggle}
											notify={notify}
										/>
									</SidebarSection>
								) : null}
							</>
						)}
					</nav>
				</ScrollArea>
			</SidebarFocusContext>
			<SidebarFooter />
			<AddPlane registered={registered} notify={notify} reveal={reveal} />
		</aside>
	);
}

/**
 * The sidebar before its node is on the tree, at boot: its two bars, the nav
 * section and skeleton rows, at the width the real one will take. The rows
 * hold off like the viewer skeleton does, so a fast boot never flashes them.
 */
export function SidebarPlaceholder() {
	const shown = useSkeleton();
	const roles = useRoles();
	const route = useRoute();
	const focus = useSidebarFocus(NAV_KEYS, selectedRow(roles, route, [], new Set()));
	const aside = useRef<HTMLElement | null>(null);
	useSidebarLinks(aside);
	return (
		<aside ref={aside} aria-label="Sidebar" className={sidebarAside}>
			<SidebarHeader />
			<SidebarFocusContext value={focus}>
				<ScrollArea className={sidebarScroll} viewportClassName={sidebarScrollViewport}>
					<nav
						aria-label="Planes"
						ref={focus.containerRef}
						className={sidebarBody}
						tabIndex={-1}
						onClick={focus.onClick}
						onKeyDown={focus.onKeyDown}
					>
						<NavSection selKey={soloPlane(route)} />
						{shown ? <SidebarSkeleton /> : null}
					</nav>
				</ScrollArea>
			</SidebarFocusContext>
			<SidebarFooter />
		</aside>
	);
}

/** The plane a solo route shows, "" for anything else. */
function soloPlane(route: Route): string {
	return route.kind === "solo" ? route.plane : "";
}

/** The selected row: on a desk item its row in its folder, solo its nav or tree row. */
function selectedRow(
	roles: ReturnType<typeof useRoles>,
	route: Route,
	rows: { key: string }[],
	folds: Set<string>,
): string | null {
	if (route.kind === "item") return selectedKey(route.desk, route.item, route.focus, folds);
	if (route.kind === "desk") return null;
	const selKey = soloPlane(route);
	const nav = NAV_ITEMS.find((item) => roles?.[item.role] === selKey);
	if (nav && selKey) return navKey(nav.role);
	return rows.some((r) => r.key === selKey) ? selKey : null;
}

/** Row-shaped placeholders, so the sidebar does not move when the tree lands. */
function SidebarSkeleton() {
	return (
		<div aria-busy="true">
			{[0, 1, 1].map((depth, i) => (
				<div
					// biome-ignore lint/suspicious/noArrayIndexKey: placeholders have no identity
					key={i}
					className={sidebarSkeletonRow}
					style={sidebarIndent(depth)}
				>
					<Skeleton className={sidebarSkeletonBar} />
				</div>
			))}
		</div>
	);
}
