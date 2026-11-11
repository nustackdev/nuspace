// The header across a pane's top: the plane's icon and trail on the left, its
// actions on the right (the pane menu, and close where the pane has one). The
// actions show on hover and on the focused pane.
//
// The trail is the planes above this one, then its own title. A parent is a
// link to its plane, so the shell's anchor rule opens it in this pane: in
// place on a desk item (written as its recent), a plain move on a solo plane.
// Past two parents the middle folds into `...`: the top plane, the parent,
// the title.
//
// Outside the body's scroll, so it stays put while the plane moves under it.
// It is the pane's drag handle (`data-pane-header`) and drags as the pane's
// row in the sidebar would: the pane in a strip, the item for a plane item,
// the plane with its params on a solo plane (../desk/drag.ts).

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
	paneCrumbHere,
	paneCrumbLink,
	paneCrumbList,
	paneCrumbParent,
	paneCrumbSep,
	paneCrumbs,
	paneHeader,
	paneHeaderActions,
	paneHeaderIcon,
	paneHeaderTitle,
} from "../design";
import { headerDragProps, type PaneAt } from "../desk/drag";
import { PlaneIcon } from "../icon/PlaneIcon";
import { planeIcon } from "../icon/parse";
import type { PlaneMeta } from "../plane/types";
import type { Crumb } from "../sidebar/api";
import { PaneMenu } from "./PaneMenu";

/** The parents a header shows: all of them up to two, else the top one, a fold, the nearest. */
export function crumbsOf(trail: readonly Crumb[]): (Crumb | "fold")[] {
	return trail.length > 2 ? [trail[0], "fold", trail[trail.length - 1]] : [...trail];
}

const SOLO: PaneAt = { kind: "solo" };

export function PaneHeader({
	at = SOLO,
	planeId,
	title,
	trail = [],
	meta,
	onMeta,
	onDelete,
	onRestart,
	onClose,
	first = true,
	focused = false,
}: {
	/** Where the pane sits: what the header drags as, and whether the menu has the column group. */
	at?: PaneAt;
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
	/** Close the pane. Left out on a solo plane: no close then. */
	onClose?: () => void;
	/** The canvas's first pane, the one the sidebar's reopen button sits over. */
	first?: boolean;
	focused?: boolean;
}) {
	return (
		<header
			className={paneHeader(first)}
			data-pane-header={planeId}
			{...headerDragProps(at, planeId)}
		>
			<span data-drag-icon className="contents">
				<PlaneIcon icon={planeIcon(meta?.icon)} className={paneHeaderIcon} />
			</span>
			<Breadcrumb className={paneCrumbs}>
				<BreadcrumbList className={paneCrumbList}>
					{crumbsOf(trail).map((c, i) => (
						<Fragment key={c === "fold" ? `fold:${i}` : c.id}>
							<BreadcrumbItem className={paneCrumbParent}>
								{c === "fold" ? (
									<BreadcrumbEllipsis />
								) : (
									<OverflowTooltip label={c.title} side="bottom">
										{/* Not draggable: a drag on the header moves the pane, not the link. */}
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
							<BreadcrumbPage data-drag-title className={paneHeaderTitle(focused)}>
								{title}
							</BreadcrumbPage>
						</OverflowTooltip>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
			<div className={paneHeaderActions}>
				<PaneMenu
					planeId={planeId}
					meta={meta}
					onChange={onMeta}
					onDelete={onDelete}
					onRestart={onRestart}
					onClose={onClose}
				/>
				{onClose ? (
					<IconButton variant="ghost" size="sm" aria-label={`Close ${title}`} onClick={onClose}>
						<X />
					</IconButton>
				) : null}
			</div>
		</header>
	);
}
