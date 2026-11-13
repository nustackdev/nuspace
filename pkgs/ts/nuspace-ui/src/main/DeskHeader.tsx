// The desk header: the row across the canvas's top while the tab is on a
// desk (an empty desk or one of its items). A solo plane has none.
//
// Left to right: the desk's icon and name, then its items in the desk's
// order, then close. An item is a link to its url, the kit's nav link: a plane item
// reads as its shown plane's icon and title, a strip as `Strip` and its pane
// count. A plane item navigated away from its original reads as the sidebar
// row does (../sidebar/DeskRows.tsx): `[icon] / [title]`, the icon the
// original's and a button that resets the item, the title the recent's. The
// item the tab shows is the active one. A click goes through the
// shell's anchor rule (../core/router.ts `paneRule`), which opens a desk item
// url, so Cmd and middle clicks stay the browser's. The items scroll sideways
// when they outgrow the header.
//
// On the right, always shown: close, which leaves the desk and keeps it: the tab
// goes to "/", which lands on home. Rename and delete are the desk folder's in
// the sidebar (../sidebar/DeskFolder.tsx).

import { cn, IconButton, NavLink, OverflowTooltip } from "@nustackdev/ui-kit";
import { Columns3, LayoutGrid, X } from "lucide-react";
import { useMemo } from "react";
import { lookOf, usePlaneLooks } from "../core/looks";
import { itemHref, leaveDesk, resetItem } from "../core/router";
import {
	deskHeader,
	deskHeaderActions,
	deskHeaderCrumbSlash,
	deskHeaderIcon,
	deskHeaderItem,
	deskHeaderItemActive,
	deskHeaderItemCount,
	deskHeaderItemGroup,
	deskHeaderItemInner,
	deskHeaderItemLabel,
	deskHeaderItems,
	deskHeaderName,
	deskHeaderReset,
} from "../design";
import { type Desk, type Item, shown } from "../desk/model";
import { PlaneIcon } from "../icon/PlaneIcon";
import { planeIcon } from "../icon/parse";
import { deskLabel, type PlaneTree, STRIP_TITLE } from "../sidebar/api";

/** How many panes a strip holds. */
function paneCount(item: Item): number {
	return item.kind === "strip" ? item.columns.reduce((n, c) => n + c.panes.length, 0) : 1;
}

export function DeskHeader({
	deskId,
	desk,
	active,
	tree,
}: {
	deskId: string;
	/** The desk as the router has it; null before it lands. */
	desk: Desk | null;
	/** The id of the item the tab shows, null on an empty desk. */
	active: string | null;
	tree: PlaneTree;
}) {
	const name = deskLabel(desk?.name ?? "");
	const items = desk?.items ?? [];
	const planes = useMemo(
		() =>
			items.flatMap((i) =>
				i.kind === "plane" ? [i.original.plane, ...(i.recent ? [i.recent.plane] : [])] : [],
			),
		[items],
	);
	const looks = usePlaneLooks(planes, tree);

	return (
		<header className={deskHeader} data-desk-header={deskId}>
			<LayoutGrid aria-hidden className={deskHeaderIcon} />
			<OverflowTooltip label={name} side="bottom">
				<span className={deskHeaderName}>{name}</span>
			</OverflowTooltip>
			<nav aria-label={`${name} items`} className={deskHeaderItems}>
				{items.map((item) => {
					const on = item.id === active;
					const href = itemHref(deskId, item.id);
					if (item.kind === "strip") {
						return (
							<NavLink
								key={item.id}
								size="sm"
								href={href}
								active={on}
								draggable={false}
								className={deskHeaderItem}
							>
								<Columns3 />
								<span className={deskHeaderItemLabel}>{STRIP_TITLE}</span>
								<span className={deskHeaderItemCount}>{paneCount(item)}</span>
							</NavLink>
						);
					}
					const look = lookOf(looks, shown(item).plane);
					if (!item.recent) {
						return (
							<NavLink
								key={item.id}
								size="sm"
								href={href}
								active={on}
								draggable={false}
								className={deskHeaderItem}
							>
								<PlaneIcon icon={planeIcon(look.icon)} />
								<span className={deskHeaderItemLabel}>{look.title}</span>
							</NavLink>
						);
					}
					const original = lookOf(looks, item.original.plane);
					return (
						<span key={item.id} className={cn(deskHeaderItemGroup, on && deskHeaderItemActive)}>
							<IconButton
								variant="ghost"
								size="xs"
								aria-label={`Reset to ${original.title}`}
								tip={`Reset to ${original.title}`}
								onClick={() => resetItem(deskId, item.id)}
								className={deskHeaderReset}
							>
								<PlaneIcon icon={planeIcon(original.icon)} />
							</IconButton>
							<span aria-hidden className={deskHeaderCrumbSlash}>
								/
							</span>
							<NavLink
								size="sm"
								href={href}
								active={on}
								draggable={false}
								className={deskHeaderItemInner}
							>
								<span className={deskHeaderItemLabel}>{look.title}</span>
							</NavLink>
						</span>
					);
				})}
			</nav>
			<div className={deskHeaderActions}>
				<IconButton
					variant="ghost"
					size="sm"
					aria-label={`Close ${name}`}
					tip="Close desk"
					onClick={leaveDesk}
				>
					<X />
				</IconButton>
			</div>
		</header>
	);
}
