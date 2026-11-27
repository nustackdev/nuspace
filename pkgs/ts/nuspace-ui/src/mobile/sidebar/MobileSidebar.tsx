// The sidebar screen: the phone's way to everything, full screen, slid in
// from the left over the plane. Swipe it left, tap the sidebar button or go
// back to close it (./open.ts); tap a row and it closes onto what the row
// opens.
//
// Top to bottom, as on desktop minus the footer: the bar (the wordmark, + for
// a new plane), Home, Search and Settings, a folder per desk, the Planes
// tree, the Specs. Rows are 44px. The data and the ops are desktop's: the
// SidebarRef node's tree and fold state (../../sidebar/state.ts), the desks
// feed and the roles (../../core/desks.ts), the sidebar ops
// (../../sidebar/ops.ts). Only the touch presentation is the phone's own.
//
//   nav       a row per role, a link to its plane
//   desks     a folder per desk, tap the title to fold; a row per item
//             (./model.ts), tap to open it. A strip is one row, its panes
//             paged through on the desk screen
//   planes    the tree, lazy like desktop's: the chevron at the row's end
//             opens a branch, the rest of the row opens the plane. Long-press a row
//             for Rename, Add plane inside, Delete (./PlaneSheet.tsx)
//   specs     a group per package, tap to open; tap an entry to make a plane
//
// No drag, no keyboard walk, no hover actions: the long-press sheet holds
// what desktop's row menus do, within v1.

import type { Path } from "@nustackdev/ui-core";
import {
	type AnchorRule,
	IconButton,
	pathKey,
	Skeleton,
	useAnchorCatcher,
} from "@nustackdev/ui-kit";
import { ChevronRight, Folder, Package, Plus } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import { useDeskOrder, useDesks, useRoles } from "../../core/desks";
import { lookOf, usePlaneLooks } from "../../core/looks";
import {
	hrefFor,
	itemHref,
	openPlane,
	paneRule,
	type Route,
	shapeOfHref,
	useRoute,
} from "../../core/router";
import { useTypePath } from "../../core/surfaces";
import { notifyOp } from "../../core/wire";
import {
	mobileChevron,
	mobileIndent,
	mobileRow,
	mobileRowEmpty,
	mobileRowIcon,
	mobileRowLabel,
	mobileRowMain,
	mobileRowNote,
	mobileSection,
	mobileSectionHead,
	mobileSidebar,
	mobileSidebarBody,
	mobileSidebarHead,
	mobileTwisty,
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
import { AddPlaneSheet, addGroups } from "./AddPlaneSheet";
import { deskPlanes, deskRows, paneCount } from "./model";
import { closeSidebar, leaveThen, useSidebarOpen } from "./open";
import { PlaneSheet, type Pressed } from "./PlaneSheet";

/**
 * A link tapped in the sidebar: closed first, then followed the way the shell
 * follows it (../../core/router.ts `paneRule`). Anything not the app's stays
 * the browser's.
 */
export const mobileSidebarRule: AnchorRule = (href, gesture, anchor, event) => {
	if (!shapeOfHref(href)) return false;
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
				<span className={sidebarWordmark}>
					<span className={sidebarWordmarkNu}>nu</span>space
				</span>
				<IconButton
					variant="ghost"
					ring="inset"
					aria-label="New plane"
					onClick={() => openAddPlane({ parent: ROOT_ID })}
					className="ml-auto size-11 [&_svg]:size-5"
				>
					<Plus />
				</IconButton>
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
					<div key={i} className={mobileRow(false)} style={mobileIndent(0)}>
						<Skeleton className="h-4 w-32" />
					</div>
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
						<div className={mobileSectionHead}>
							<span>Planes</span>
							<IconButton
								variant="ghost"
								size="sm"
								ring="inset"
								aria-label="New plane"
								onClick={() => openAddPlane({ parent: ROOT_ID })}
								className="ml-auto"
							>
								<Plus />
							</IconButton>
						</div>
						<div>
							{rows.length ? null : (
								<button
									type="button"
									className={mobileRow(false)}
									style={mobileIndent(0)}
									onClick={() => openAddPlane({ parent: ROOT_ID })}
								>
									<Plus aria-hidden="true" className={mobileRowIcon} />
									<span className={mobileRowLabel}>Add a plane</span>
								</button>
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
					<a
						key={role}
						href={plane ? hrefFor(plane) : undefined}
						aria-current={plane && plane === selected ? "page" : undefined}
						data-nav={role}
						className={mobileRow(!!plane && plane === selected)}
						style={mobileIndent(0)}
					>
						<Icon aria-hidden="true" className={mobileRowIcon} />
						<span className={mobileRowLabel}>{label}</span>
					</a>
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
	const on = route.kind === "item" ? route.item.id : "";

	return (
		<section aria-label="Desks" className={mobileSection}>
			<div className={mobileSectionHead}>Desks</div>
			{list.map(({ id, desk }) => {
				const folded = folds.has(folderKey(id));
				const rows = deskRows(desk);
				return (
					<div key={id}>
						<button
							type="button"
							aria-expanded={!folded}
							data-desk={id}
							className={mobileRow(false)}
							style={mobileIndent(0)}
							onClick={() => setFolded(folderKey(id), !folded)}
						>
							<Folder aria-hidden="true" className={mobileRowIcon} />
							<span className={mobileRowLabel}>{deskLabel(desk.name)}</span>
							<ChevronRight aria-hidden="true" className={mobileChevron(!folded)} />
						</button>
						{folded ? null : rows.length ? (
							rows.map((row) => {
								const look = lookOf(looks, row.plane);
								return (
									<a
										key={row.item}
										href={itemHref(id, row.item)}
										aria-current={row.item === on ? "page" : undefined}
										data-item={row.item}
										className={mobileRow(row.item === on)}
										style={mobileIndent(1)}
									>
										<PlaneIcon icon={planeIcon(look.icon)} className={mobileRowIcon} />
										<span className={mobileRowLabel}>{look.title}</span>
										{row.strip ? (
											<span className={mobileRowNote}>{paneCount(row.panes)}</span>
										) : null}
									</a>
								);
							})
						) : (
							<div className={mobileRowEmpty} style={mobileIndent(1)}>
								Empty desk
							</div>
						)}
					</div>
				);
			})}
		</section>
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
			<div
				data-plane-row={row.id}
				className={mobileRow(selected)}
				style={mobileIndent(row.depth)}
				{...press}
			>
				<a
					href={hrefFor(row.id)}
					aria-current={selected ? "page" : undefined}
					className={mobileRowMain}
				>
					<PlaneIcon icon={planeIcon(row.icon)} className={mobileRowIcon} />
					<span className={mobileRowLabel}>{row.title}</span>
				</a>
				<button
					type="button"
					aria-label={row.open ? `Close ${row.title}` : `Open ${row.title}`}
					className={mobileTwisty}
					onClick={onToggle}
				>
					<ChevronRight aria-hidden="true" className={mobileChevron(row.open)} />
				</button>
			</div>
			{showsNoPlanes(row) ? (
				<div className={mobileRowEmpty} style={mobileIndent(row.depth + 1)}>
					No planes inside
				</div>
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
			<div className={mobileSectionHead}>Specs</div>
			{groups.map(({ pkg, entries }) => {
				const key = groupKey(pkg);
				const open = expanded.has(key);
				return (
					<div key={pkg}>
						<button
							type="button"
							aria-expanded={open}
							className={mobileRow(false)}
							style={mobileIndent(0)}
							onClick={() => toggle(key)}
						>
							<Package aria-hidden="true" className={mobileRowIcon} />
							<span className={mobileRowLabel}>{pkg}</span>
							<ChevronRight aria-hidden="true" className={mobileChevron(open)} />
						</button>
						{open
							? entries.map((entry) => (
									<button
										key={entry.name}
										type="button"
										className={mobileRow(false)}
										style={mobileIndent(1)}
										onClick={() => make(entry)}
									>
										<PlaneIcon icon={planeIcon(entry.icon)} className={mobileRowIcon} />
										<span className={mobileRowLabel}>{entry.label}</span>
									</button>
								))
							: null}
					</div>
				);
			})}
		</section>
	);
}
