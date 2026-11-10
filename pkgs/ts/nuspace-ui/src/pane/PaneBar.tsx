// The bar across a pane's top: the plane's trail, its settings, and close.
// Every pane on the desk has one, so the title is part of the pane and scrolls
// with it; the dock under the desk (../main/Dock.tsx) is only a map.
//
// The trail is the planes above this one, then its own title. A parent is a
// link to its plane, so the shell's anchor rule opens it: in this pane, which
// a press on the bar has just focused, or beside it with Option. Past three
// steps the middle folds into `...`: the top plane, the parent, the title.
//
// Outside the plane's scroll, so it stays put while the plane moves under it.
// With more than one pane the bar drags its pane along the desk, the way a
// window moves by its title bar: the drop is ../main/useCanvasDrop.ts.

import {
	Breadcrumb,
	BreadcrumbEllipsis,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
	IconButton,
	OverflowTooltip,
} from "@nustackdev/ui-kit";
import { X } from "lucide-react";
import { Fragment } from "react";
import { hrefFor } from "../core/router";
import {
	paneBar,
	paneBarTitle,
	paneCrumbHere,
	paneCrumbLink,
	paneCrumbList,
	paneCrumbParent,
	paneCrumbSep,
	paneCrumbs,
} from "../design";
import type { PlaneMeta } from "../plane/types";
import type { Crumb } from "../sidebar/api";
import { PaneMenu } from "./PaneMenu";

/** What a pane's drag by its bar carries: its plane id. */
export const PANE_MIME = "application/x-nuspace-pane";

/** The parents a bar shows: all of them up to two, else the top one, a fold, the nearest. */
export function crumbsOf(trail: readonly Crumb[]): (Crumb | "fold")[] {
	return trail.length > 2 ? [trail[0], "fold", trail[trail.length - 1]] : [...trail];
}

export function PaneBar({
	planeId,
	title,
	trail = [],
	meta,
	onMeta,
	onDelete,
	onRestart,
	onClose,
	first = true,
	movable = false,
	closable = true,
	lit = false,
}: {
	planeId: string;
	title: string;
	/** The planes above this one, top first, each with a title to show. */
	trail?: readonly Crumb[];
	/** Null while the plane is loading. */
	meta: PlaneMeta | null;
	onMeta: (patch: Record<string, unknown>) => void;
	/** Left out for a Plane that cannot be deleted. */
	onDelete?: () => void;
	/** Run the plane again. Left out for an absent pane: nothing runs there. */
	onRestart?: () => void;
	onClose: () => void;
	/** The desk's first pane, the one the rail's reopen button sits over. */
	first?: boolean;
	/** More than one pane: the bar drags its pane along the desk. */
	movable?: boolean;
	/** Draw the close button. Not on a lone pane: there is nothing to close it to. */
	closable?: boolean;
	/** Bring the title up a tier: the focused pane of several. */
	lit?: boolean;
}) {
	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: dragging a pane by its bar is a mouse shortcut; the order is the route's, not the bar's
		<header
			className={paneBar(first, movable)}
			draggable={movable}
			onDragStart={(e) => {
				e.dataTransfer.effectAllowed = "move";
				e.dataTransfer.setData(PANE_MIME, planeId);
			}}
		>
			<Breadcrumb className={paneCrumbs}>
				<BreadcrumbList className={paneCrumbList}>
					{crumbsOf(trail).map((c, i) => (
						<Fragment key={c === "fold" ? `fold:${i}` : c.id}>
							<BreadcrumbItem className={paneCrumbParent}>
								{c === "fold" ? (
									<BreadcrumbEllipsis />
								) : (
									<OverflowTooltip label={c.title} side="bottom">
										{/* Not draggable: a drag on the bar moves the pane, not the link. */}
										<BreadcrumbLink
											className={paneCrumbLink}
											href={hrefFor(c.id)}
											draggable={false}
										>
											{c.title}
										</BreadcrumbLink>
									</OverflowTooltip>
								)}
							</BreadcrumbItem>
							<BreadcrumbSeparator className={paneCrumbSep} />
						</Fragment>
					))}
					<BreadcrumbItem className={paneCrumbHere}>
						<OverflowTooltip label={title} side="right">
							<BreadcrumbPage className={paneBarTitle(lit)}>{title}</BreadcrumbPage>
						</OverflowTooltip>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
			<PaneMenu
				planeId={planeId}
				meta={meta}
				onChange={onMeta}
				onDelete={onDelete}
				onRestart={onRestart}
			/>
			{closable ? (
				<IconButton variant="ghost" size="sm" aria-label={`Close ${title}`} onClick={onClose}>
					<X />
				</IconButton>
			) : null}
		</header>
	);
}
