// The sidebar screen: the phone's way to everything, full screen, slid in
// from the left over the plane. Swipe it left, tap the sidebar button or go
// back to close it (./open.ts); tap a row and it closes onto what the row
// opens.
//
// Top to bottom, as on desktop minus the footer: the header every screen
// wears (../Header.tsx: the wordmark, + for a new plane), then the sections,
// desktop's: the nav, a section per desk, Planes, Specs. Every group is one
// section (./Section.tsx), every line one row (./Row.tsx): 44px, one icon
// size, one label edge a depth, every chevron and + in one column, titles
// and rows alike. The data and the ops
// are desktop's: the SidebarRef node's tree and fold state
// (../../sidebar/state.ts), the desks feed and the roles
// (../../core/desks.ts), the desk folds (../../sidebar/folders.ts), the
// sidebar ops (../../sidebar/ops.ts). Only the touch presentation is the
// phone's own.
//
//   nav       no title: a row per role, a link to its plane
//   a desk    titled with the desk's name, tap the title to fold; a row per
//             item (./model.ts) at depth 0: a plane item opens as itself; a
//             strip, its planes' icons as one composite and their titles on
//             one line (./Strip.tsx), opens the desk pager on its first pane
//   Planes    + in the title's trail; the tree, lazy like desktop's: the
//             chevron at the row's end opens a branch, the rest of the row
//             opens the plane. Long-press a row for Rename, Add plane
//             inside, Delete (./PlaneSheet.tsx)
//   Specs     a group per package, tap to open; tap an entry to make a plane
//
// No drag, no keyboard walk, no hover actions: the long-press sheet holds
// what desktop's row menus do, within v1.

import type { Path } from "@nustackdev/ui-core";
import { type AnchorRule, pathKey, Skeleton, useAnchorCatcher } from "@nustackdev/ui-kit";
import { Package, Plus } from "lucide-react";
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
	mobileSidebar,
	mobileSidebarBody,
	mobileSidebarList,
	sidebarWordmark,
	sidebarWordmarkNu,
} from "../../design";
import { PlaneIcon } from "../../icon/PlaneIcon";
import { planeIcon } from "../../icon/parse";
import { createPlane, openAddPlane } from "../../sidebar/add";
import { deskLabel, folderKey, setFolded, useFolds } from "../../sidebar/folders";
import { NAV_ITEMS, rolePlanes } from "../../sidebar/nav";
import type { Notify, Ops } from "../../sidebar/ops";
import { patchSidebar, useExpanded, useSidebarValue } from "../../sidebar/state";
import { showsNoPlanes, visibleRows } from "../../sidebar/tree";
import { childrenOf, type Registered, ROOT_ID, rootId } from "../../sidebar/types";
import { useLongPress, useSwipeClose } from "../gestures";
import { HeaderButton, MobileHeader } from "../Header";
import { AddPlaneSheet, addGroups } from "./AddPlaneSheet";
import { type DeskRow, deskPlanes, deskRows } from "./model";
import { closeSidebar, leaveThen, useSidebarOpen } from "./open";
import { PlaneSheet, type Pressed } from "./PlaneSheet";
import { MobileRow, RowAdd, RowChevron, RowFold } from "./Row";
import { MobileSection } from "./Section";
import { StripIcon, StripLabel } from "./Strip";

/** The attribute a desk's strip row carries: the plane a tap focuses. */
export const PANE_ATTR = "data-pane";

/**
 * A link tapped in the sidebar: closed first, then followed the way the shell
 * follows it (../../core/router.ts `paneRule`), a desk's strip rows
 * through `openPane`. Anything not the app's stays the browser's.
 */
export const mobileSidebarRule: AnchorRule = (href, gesture, anchor, event) => {
	const hit = shapeOfHref(href);
	if (!hit) return false;
	// A strip row: the pager on its pane, as desktop's pane row opens it.
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
			<MobileHeader
				label="nuspace"
				title={
					<span className={sidebarWordmark}>
						<span className={sidebarWordmarkNu}>nu</span>space
					</span>
				}
				actions={
					<HeaderButton label="New plane" onClick={() => openAddPlane({ parent: ROOT_ID })}>
						<Plus />
					</HeaderButton>
				}
			/>
			{path ? <SidebarBody path={path} /> : <SidebarBooting />}
		</aside>
	);
}

/** Before the SidebarRef node lands: the nav rows, and row-shaped placeholders. */
function SidebarBooting() {
	return (
		<nav aria-label="Planes" className={mobileSidebarBody}>
			<div className={mobileSidebarList}>
				<NavRows route={useRoute()} />
				<div aria-busy="true">
					{[0, 1, 2].map((i) => (
						<MobileRow
							key={i}
							icon={<Skeleton className="size-5 rounded-md" />}
							label={<Skeleton className="h-4 w-32" />}
						/>
					))}
				</div>
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
			<div className={mobileSidebarList}>
				<NavRows route={route} />
				{loading ? null : (
					<>
						<DeskSections route={route} />
						<MobileSection
							label="Planes"
							title="Planes"
							trail={<RowAdd label="New plane" onClick={() => openAddPlane({ parent: ROOT_ID })} />}
						>
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
						</MobileSection>
						<Specs registered={registered} expanded={expanded} toggle={toggle} notify={notify} />
					</>
				)}
			</div>
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
		<MobileSection label="Navigation">
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
		</MobileSection>
	);
}

// -- Desks ----------------------------------------------------------------------

/** A section per desk, in the desks' order: titled with its name, folding, its items. */
function DeskSections({ route }: { route: Route }) {
	const desks = useDesks();
	const order = useDeskOrder();
	const folds = useFolds();
	const list = useMemo(
		() => order.flatMap((id) => (desks?.[id] ? [{ id, desk: desks[id] }] : [])),
		[desks, order],
	);
	const looks = usePlaneLooks(useMemo(() => deskPlanes(list.map((d) => d.desk)), [list]));

	return list.map(({ id, desk }) => {
		const name = deskLabel(desk.name);
		const rows = deskRows(desk);
		// The item the screen shows.
		const on = route.kind === "item" && route.desk === id ? route.item.id : "";
		return (
			<MobileSection
				key={id}
				label={name}
				title={name}
				head={{ "data-desk": id }}
				folded={folds.has(folderKey(id))}
				onFold={(folded) => setFolded(folderKey(id), folded)}
			>
				{rows.length ? (
					rows.map((r) => (
						<DeskItemRow
							key={r.item.id}
							deskId={id}
							at={r}
							looks={looks}
							selected={r.item.id === on}
						/>
					))
				) : (
					<MobileRow kind="note" label="Empty desk" />
				)}
			</MobileSection>
		);
	});
}

/**
 * One row of a desk section: a desk item, one line like any row. A plane
 * item opens as itself. A strip opens the desk pager on its first pane
 * (`PANE_ATTR`, which `mobileSidebarRule` reads): its planes' icons as one
 * composite in the lead, their titles on the line.
 */
function DeskItemRow({
	deskId,
	at,
	looks,
	selected,
}: {
	deskId: string;
	at: DeskRow;
	looks: Record<string, PlaneLook>;
	selected: boolean;
}) {
	const { item, planes, pane } = at;
	const common = {
		as: "a" as const,
		href: itemHref(deskId, item.id),
		"aria-current": selected ? ("page" as const) : undefined,
		selected,
		"data-item": item.id,
	};
	if (item.kind === "plane") {
		const look = lookOf(looks, planes[0] ?? "");
		return (
			<MobileRow {...common} icon={<PlaneIcon icon={planeIcon(look.icon)} />} label={look.title} />
		);
	}
	const shown = planes.map((p) => lookOf(looks, p));
	const titles = shown.map((l) => l.title);
	return (
		<MobileRow
			{...common}
			{...{ [PANE_ATTR]: pane || undefined }}
			aria-label={titles.join(", ")}
			icon={<StripIcon icons={shown.map((l) => l.icon)} />}
			label={<StripLabel titles={titles} />}
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
		<MobileSection label="Specs" title="Specs">
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
		</MobileSection>
	);
}
