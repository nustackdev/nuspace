// The rail: what the sidebar folds to. One narrow column of icons on the
// window's left edge. The shell's sidebar panel folds to its width and holds
// it next to the open sidebar, showing whichever its fold says
// (../shell/Shell.tsx).
//
// Top to bottom: the toggle that brings the sidebar back, then the sidebar's
// first level only, a hairline between the groups:
//
//   nav      home, search, settings
//   desks    one per desk, its name's first letter; a click opens the desk
//            (its first item, ../core/router.ts `openDesk` through its url)
//   planes   the top-level planes of the tree, by their icons
//
// No footer, no specs, no folds, no menus, no drag. Every icon is a link like
// the sidebar's rows, so the shell's catcher routes a plain click and a Cmd
// click stays the browser's. A tooltip on the right names it.
//
// Selected, one look for all, like the sidebar: the nav icon of a solo role
// plane, the desk the tab shows, and on a solo plane deeper in the tree its
// top-level ancestor, so the rail always says where you are.

import { cn, IconButton, ScrollArea, Shortcut } from "@nustackdev/ui-kit";
import type * as React from "react";
import { useMemo } from "react";
import { type Roles, useDeskOrder, useDesks, useRoles } from "../core/desks";
import { deskHref, hrefFor, type Route, useRoute } from "../core/router";
import {
	sidebarChromeButton,
	sidebarRail,
	sidebarRailBody,
	sidebarRailDivider,
	sidebarRailHead,
	sidebarRailItem,
	sidebarRailMonogram,
	sidebarRailScroll,
	sidebarScrollViewport,
	sidebarTooltipHint,
} from "../design";
import { PlaneIcon } from "../icon/PlaneIcon";
import { planeIcon } from "../icon/parse";
import { focusSidebarToggle, setSidebarCollapsed } from "./collapse";
import { deskLabel } from "./folders";
import { NAV_ITEMS, rolePlanes } from "./nav";
import { SidebarToggle } from "./SidebarHeader";
import { childrenOf, KIND_PLANE, type PlaneTree, ROOT_ID, rootId } from "./types";

export function SidebarRail({ tree }: { tree: PlaneTree }) {
	const roles = useRoles();
	const route = useRoute();
	const desks = useDesks();
	const order = useDeskOrder();
	const hidden = useMemo(() => rolePlanes(roles), [roles]);
	const planes = useMemo(
		() => childrenOf(tree, rootId(tree)).filter((r) => r.kind === KIND_PLANE && !hidden.has(r.id)),
		[tree, hidden],
	);
	const deskList = order.flatMap((id) => (desks?.[id] ? [{ id, desk: desks[id] }] : []));
	const top = topOf(tree, route);

	return (
		<aside aria-label="Sidebar" className={sidebarRail}>
			<div className={sidebarRailHead}>
				<SidebarToggle
					label="Show sidebar"
					onClick={() => {
						setSidebarCollapsed(false);
						focusSidebarToggle();
					}}
				/>
			</div>
			<ScrollArea className={sidebarRailScroll} viewportClassName={sidebarScrollViewport}>
				<nav aria-label="Planes" className={sidebarRailBody}>
					{NAV_ITEMS.map(({ role, label, icon: Icon, keys }) => {
						const plane = roles?.[role] ?? "";
						return (
							<RailLink
								key={role}
								href={plane ? hrefFor(plane) : undefined}
								label={label}
								keys={keys}
								selected={isRole(roles, role, route)}
							>
								<Icon aria-hidden="true" />
							</RailLink>
						);
					})}
					{deskList.length ? <hr className={sidebarRailDivider} /> : null}
					{deskList.map(({ id, desk }) => {
						const name = deskLabel(desk.name);
						return (
							<RailLink
								key={id}
								href={deskHref(id)}
								label={name}
								selected={(route.kind === "desk" || route.kind === "item") && route.desk === id}
							>
								<span aria-hidden="true" className={sidebarRailMonogram}>
									{[...name][0]?.toUpperCase()}
								</span>
							</RailLink>
						);
					})}
					{planes.length ? <hr className={sidebarRailDivider} /> : null}
					{planes.map((row) => (
						<RailLink
							key={row.id}
							href={hrefFor(row.id)}
							label={row.title || "Untitled"}
							selected={top === row.id}
						>
							<PlaneIcon icon={planeIcon(row.icon)} />
						</RailLink>
					))}
				</nav>
			</ScrollArea>
		</aside>
	);
}

function RailLink({
	href,
	label,
	keys,
	selected,
	children,
}: {
	href: string | undefined;
	label: string;
	keys?: readonly string[];
	selected: boolean;
	children: React.ReactNode;
}) {
	return (
		<IconButton
			asChild
			variant="ghost"
			size="sm"
			ring="inset"
			aria-label={label}
			tipSide="right"
			tip={
				<>
					{label}
					{keys ? <Shortcut keys={keys} size="sm" className={sidebarTooltipHint} /> : null}
				</>
			}
			className={cn(sidebarChromeButton, sidebarRailItem(selected))}
		>
			<a href={href} aria-current={selected ? "page" : undefined}>
				{children}
			</a>
		</IconButton>
	);
}

/** Whether the tab shows `role`'s plane solo. */
function isRole(roles: Roles | null, role: keyof Roles, route: Route): boolean {
	const plane = roles?.[role];
	return !!plane && route.kind === "solo" && route.plane === plane;
}

/** The top-level plane a solo route's plane hangs under (itself when top-level), "" for none. */
function topOf(tree: PlaneTree, route: Route): string {
	if (route.kind !== "solo") return "";
	let id = route.plane;
	for (let hops = 0; hops < 256; hops++) {
		const row = tree[id];
		if (!row || row.parent === id) return "";
		if (row.parent === ROOT_ID || tree[row.parent]?.parent === row.parent) return id;
		id = row.parent;
	}
	return "";
}
