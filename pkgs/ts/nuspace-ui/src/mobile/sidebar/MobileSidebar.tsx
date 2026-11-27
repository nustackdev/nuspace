// The sidebar screen: the phone's way to everything, full screen, slid in
// from the left over the plane. Swipe it left, tap the sidebar button or go
// back to close it (./open.ts); tap a row and it closes onto what the row
// opens.
//
// Top to bottom, as on desktop minus the footer: the bar (the wordmark, + for
// a new plane), Home, Search and Settings, a folder per desk, the Planes
// tree, the Specs. Every line is one row (./Row.tsx): 44px, one icon size,
// one label edge a depth, every chevron and + in one column. The data and the ops are desktop's: the
// SidebarRef node's tree and fold state (../../sidebar/state.ts), the desks
// feed and the roles (../../core/desks.ts), the sidebar ops
// (../../sidebar/ops.ts). Only the touch presentation is the phone's own.
//
//   nav       a row per role, a link to its plane
//   desks     a folder per desk, tap the title to fold; its rows as
//             desktop's (./model.ts): a plane item opens as itself; a
//             Strip, a Column (2+ panes) and a pane open the desk pager on
//             their pane, the strip and column folding by their chevron
//   planes    the tree, lazy like desktop's: the chevron at the row's end
//             opens a branch, the rest of the row opens the plane. Long-press a row
//             for Rename, Add plane inside, Delete (./PlaneSheet.tsx)
//   specs     a group per package, tap to open; tap an entry to make a plane
//
// No drag, no keyboard walk, no hover actions: the long-press sheet holds
// what desktop's row menus do, within v1.

import type { Path } from "@nustackdev/ui-core";
import { type AnchorRule, pathKey, Skeleton, useAnchorCatcher } from "@nustackdev/ui-kit";
import { Columns3, Folder, Package, Plus, Rows3 } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import { useDeskOrder, useDesks, useRoles } from "../../core/desks";
import { lookOf, type PlaneLook, usePlaneLooks } from "../../core/looks";
import {
	hrefFor,
	itemHref,
	openPane,
	openPlane,
	paneRule,
	type Route,
	shapeOfHref,
	useRoute,
} from "../../core/router";
import { useTypePath } from "../../core/surfaces";
import { notifyOp } from "../../core/wire";
import {
	mobileSection,
	mobileSidebar,
	mobileSidebarBody,
	mobileSidebarHead,
	sidebarWordmark,
	sidebarWordmarkNu,
} from "../../design";
import { shown } from "../../desk/model";
import { PlaneIcon } from "../../icon/PlaneIcon";
import { planeIcon } from "../../icon/parse";
import { createPlane, openAddPlane } from "../../sidebar/add";
import {
	COLUMN_TITLE,
	deskLabel,
	folderKey,
	STRIP_TITLE,
	selectedKey,
	setFolded,
	useFolds,
} from "../../sidebar/folders";
import { NAV_ITEMS, rolePlanes } from "../../sidebar/nav";
import type { Notify, Ops } from "../../sidebar/ops";
import { patchSidebar, useExpanded, useSidebarValue } from "../../sidebar/state";
import { showsNoPlanes, visibleRows } from "../../sidebar/tree";
import { childrenOf, type Registered, ROOT_ID, rootId } from "../../sidebar/types";
import { useLongPress, useSwipeClose } from "../gestures";
import { AddPlaneSheet, addGroups } from "./AddPlaneSheet";
import { type DeskRow, deskPlanes, deskRows } from "./model";
import { closeSidebar, leaveThen, useSidebarOpen } from "./open";
import { PlaneSheet, type Pressed } from "./PlaneSheet";
import { MobileRow, RowAdd, RowChevron, RowFold } from "./Row";

/** The attribute a desk folder's strip, column or pane row carries: the plane a tap focuses. */
export const PANE_ATTR = "data-pane";

/**
 * A link tapped in the sidebar: closed first, then followed the way the shell
 * follows it (../../core/router.ts `paneRule`), a desk folder's pane rows
 * through `openPane`. Anything not the app's stays the browser's.
 */
export const mobileSidebarRule: AnchorRule = (href, gesture, anchor, event) => {
	const hit = shapeOfHref(href);
	if (!hit) return false;
	// A strip, column or pane row: the pager on its pane, as desktop's pane row opens it.
	const pane = anchor.closest(`[${PANE_ATTR}]`)?.getAttribute(PANE_ATTR);
	if (pane && hit.shape.kind === "item" && gesture === "plain") {
		const { desk, item } = hit.shape;
		leaveThen(() => openPane(desk, item, pane));
		return true;
	}
	leaveThen(() => paneRule(href, gesture, anchor, event));
	return true;
};

/** The sidebar screen, at the SidebarRef node once it lands; the nav rows alone before. */
export function MobileSidebar() {
	const path = useTypePath("SidebarRef");
	const open = useSidebarOpen();
	const panel = useRef<HTMLElement | null>(null);
	useAnchorCatcher(panel, mobileSidebarRule);
	useSwipeClose(panel, open, closeSidebar);

	return (
		<aside
			ref={panel}
			aria-label="Sidebar"
			inert={!open}
			data-sidebar-screen={open ? "open" : "closed"}
			className={mobileSidebar(open)}
		>
			<div className={mobileSidebarHead}>
				<MobileRow
					kind="bar"
					label={
						<span className={sidebarWordmark}>
							<span className={sidebarWordmarkNu}>nu</span>space
						</span>
					}
					trail={<RowAdd label="New plane" onClick={() => openAddPlane({ parent: ROOT_ID })} />}
				/>
			</div>
			{path ? <SidebarBody path={path} /> : <SidebarBooting />}
		</aside>
	);
}

/** Before the SidebarRef node lands: the nav rows, and row-shaped placeholders. */
function SidebarBooting() {
	return (
		<nav aria-label="Planes" className={mobileSidebarBody}>
			<NavRows route={useRoute()} />
			<div aria-busy="true" className={mobileSection}>
				{[0, 1, 2].map((i) => (
					<MobileRow
						key={i}
						icon={<Skeleton className="size-5 rounded-md" />}
						label={<Skeleton className="h-4 w-32" />}
					/>
				))}
			</div>
		</nav>
	);
}

function SidebarBody({ path }: { path: Path }) {
	const { tree, loaded, registered } = useSidebarValue(path);
	const expandedList = useExpanded(path);
	const expanded = useMemo(() => new Set(expandedList), [expandedList]);
	const roles = useRoles();
	const route = useRoute();
	const key = pathKey(path);
	const [pressed, setPressed] = useState<Pressed>(null);

	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const notify: Notify = useCallback(
		<K extends keyof Ops & string>(op: K, args: Ops[K]) => notifyOp<Ops, K>(path, op, args),
		[key],
	);

	// Open or close a branch (a plane, or a specs group), and tell the server, as desktop does.
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const setOpen = useCallback(
		(id: string, open: boolean) => {
			patchSidebar(path, (s) => {
				const next = new Set(s.expanded);
				if (open) next.add(id);
				else next.delete(id);
				return { expanded: Array.from(next) };
			});
			notify(open ? "plane.expand" : "plane.collapse", { plane_id: id });
		},
		[key, notify],
	);
	const toggle = (id: string) => setOpen(id, !expanded.has(id));
	const expand = useCallback((id: string) => setOpen(id, true), [setOpen]);

	const hidden = useMemo(() => rolePlanes(roles), [roles]);
	const rows = useMemo(
		() => visibleRows(tree, childrenOf(tree, rootId(tree)), expanded, hidden),
		[tree, expanded, hidden],
	);
	const loading = !loaded || !rootId(tree);
	const selected = route.kind === "solo" ? route.plane : "";

	return (
		<nav aria-label="Planes" className={mobileSidebarBody}>
			<NavRows route={route} />
			{loading ? null : (
				<>
					<DeskFolders route={route} />
					<section aria-label="Planes" className={mobileSection}>
						<MobileRow
							kind="head"
							label="Planes"
							trail={<RowAdd label="New plane" onClick={() => openAddPlane({ parent: ROOT_ID })} />}
						/>
						<div>
							{rows.length ? null : (
								<MobileRow
									as="button"
									icon={<Plus />}
									label="Add a plane"
									onClick={() => openAddPlane({ parent: ROOT_ID })}
								/>
							)}
							{rows.map((row) => (
								<PlaneRow
									key={row.key}
									row={row}
									selected={row.id === selected}
									onToggle={() => toggle(row.id)}
									onPress={() => setPressed({ id: row.id, step: "actions" })}
								/>
							))}
						</div>
					</section>
					<Specs registered={registered} expanded={expanded} toggle={toggle} notify={notify} />
				</>
			)}
			<PlaneSheet tree={tree} pressed={pressed} onPressed={setPressed} notify={notify} />
			<AddPlaneSheet registered={registered} notify={notify} expand={expand} />
		</nav>
	);
}

// -- Nav ------------------------------------------------------------------------

function NavRows({ route }: { route: Route }) {
	const roles = useRoles();
	const selected = route.kind === "solo" ? route.plane : "";
	return (
		<section aria-label="Navigation" className={mobileSection}>
			{NAV_ITEMS.map(({ role, label, icon: Icon }) => {
				const plane = roles?.[role] ?? "";
				return (
					<MobileRow
						key={role}
						as="a"
						href={plane ? hrefFor(plane) : undefined}
						aria-current={plane && plane === selected ? "page" : undefined}
						data-nav={role}
						selected={!!plane && plane === selected}
						icon={<Icon />}
						label={label}
					/>
				);
			})}
		</section>
	);
}

// -- Desks ----------------------------------------------------------------------

function DeskFolders({ route }: { route: Route }) {
	const desks = useDesks();
	const order = useDeskOrder();
	const folds = useFolds();
	const list = useMemo(
		() => order.flatMap((id) => (desks?.[id] ? [{ id, desk: desks[id] }] : [])),
		[desks, order],
	);
	const looks = usePlaneLooks(useMemo(() => deskPlanes(list.map((d) => d.desk)), [list]));
	if (!list.length) return null;

	return (
		<section aria-label="Desks" className={mobileSection}>
			<MobileRow kind="head" label="Desks" />
			{list.map(({ id, desk }) => {
				const folded = folds.has(folderKey(id));
				const rows = deskRows(id, desk, folds);
				// The row of what the screen shows, as desktop picks it.
				const on =
					route.kind === "item" && route.desk === id
						? selectedKey(id, route.item, route.focus, folds)
						: "";
				return (
					<div key={id}>
						<MobileRow
							as="button"
							aria-expanded={!folded}
							data-desk={id}
							onClick={() => setFolded(folderKey(id), !folded)}
							icon={<Folder />}
							label={deskLabel(desk.name)}
							trail={<RowChevron open={!folded} />}
						/>
						{folded ? null : rows.length ? (
							rows.map((r) => (
								<DeskFolderRow key={r.row.key} deskId={id} at={r} looks={looks} on={on} />
							))
						) : (
							<MobileRow kind="note" depth={1} label="Empty desk" />
						)}
					</div>
				);
			})}
		</section>
	);
}

/**
 * One row of a desk folder, by kind, as desktop's folder draws them
 * (../../sidebar/DeskRows.tsx). A plane item opens as itself; a strip, a
 * column and a pane open the desk pager on their pane (`PANE_ATTR`, which
 * `mobileSidebarRule` reads). A strip or column folds by its chevron.
 */
function DeskFolderRow({
	deskId,
	at,
	looks,
	on,
}: {
	deskId: string;
	at: DeskRow;
	looks: Record<string, PlaneLook>;
	on: string;
}) {
	const { row, depth, pane } = at;
	const selected = row.key === on;
	const href = itemHref(deskId, row.item);
	const common = {
		depth,
		selected,
		"data-item": row.item,
		[PANE_ATTR]: pane || undefined,
		"data-page": row.kind === "plane" ? undefined : at.page,
	};
	if (row.kind === "plane" || row.kind === "pane") {
		const look = lookOf(looks, shown(row.links).plane);
		return (
			<MobileRow
				{...common}
				as="a"
				href={href}
				aria-current={selected ? "page" : undefined}
				icon={<PlaneIcon icon={planeIcon(look.icon)} />}
				label={look.title}
			/>
		);
	}
	const strip = row.kind === "strip";
	const name = strip ? "strip" : "column";
	return (
		<MobileRow
			{...common}
			main={{ href, current: selected }}
			icon={strip ? <Columns3 /> : <Rows3 />}
			label={strip ? STRIP_TITLE : COLUMN_TITLE}
			trail={
				<RowFold
					open={row.open}
					label={row.open ? `Collapse ${name}` : `Expand ${name}`}
					onClick={() => setFolded(row.key, row.open)}
				/>
			}
		/>
	);
}

// -- Planes ---------------------------------------------------------------------

function PlaneRow({
	row,
	selected,
	onToggle,
	onPress,
}: {
	row: ReturnType<typeof visibleRows>[number];
	selected: boolean;
	onToggle: () => void;
	onPress: () => void;
}) {
	const press = useLongPress(onPress);
	return (
		<>
			<MobileRow
				data-plane-row={row.id}
				selected={selected}
				depth={row.depth}
				main={{ href: hrefFor(row.id), current: selected }}
				icon={<PlaneIcon icon={planeIcon(row.icon)} />}
				label={row.title}
				trail={
					<RowFold
						open={row.open}
						label={row.open ? `Close ${row.title}` : `Open ${row.title}`}
						onClick={onToggle}
					/>
				}
				{...press}
			/>
			{showsNoPlanes(row) ? (
				<MobileRow kind="note" depth={row.depth + 1} label="No planes inside" />
			) : null}
		</>
	);
}

// -- Specs ----------------------------------------------------------------------

/** The fold key of a package's group, as desktop's Specs keeps it. */
const groupKey = (pkg: string) => `ext:${pkg}`;

function Specs({
	registered,
	expanded,
	toggle,
	notify,
}: {
	registered: Registered[];
	expanded: Set<string>;
	toggle: (key: string) => void;
	notify: Notify;
}) {
	const groups = useMemo(() => addGroups(registered).filter((g) => g.pkg), [registered]);
	if (!groups.length) return null;
	const make = (entry: Registered) => {
		const planeId = createPlane(notify, entry);
		leaveThen(() => openPlane(planeId));
	};
	return (
		<section aria-label="Specs" className={mobileSection}>
			<MobileRow kind="head" label="Specs" />
			{groups.map(({ pkg, entries }) => {
				const key = groupKey(pkg);
				const open = expanded.has(key);
				return (
					<div key={pkg}>
						<MobileRow
							as="button"
							aria-expanded={open}
							onClick={() => toggle(key)}
							icon={<Package />}
							label={pkg}
							trail={<RowChevron open={open} />}
						/>
						{open
							? entries.map((entry) => (
									<MobileRow
										key={entry.name}
										as="button"
										depth={1}
										onClick={() => make(entry)}
										icon={<PlaneIcon icon={planeIcon(entry.icon)} />}
										label={entry.label}
									/>
								))
							: null}
					</div>
				);
			})}
		</section>
	);
}
