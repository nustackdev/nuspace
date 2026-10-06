// The bar across a pane's top: the plane's title, its settings, and close.
// Every pane on the desk has one, so the title is part of the pane and scrolls
// with it; the dock under the desk (../main/Dock.tsx) is only a map.
//
// Outside the plane's scroll, so it stays put while the plane moves under it.
// With more than one pane the bar drags its pane along the desk, the way a
// window moves by its title bar: the drop is ../main/useCanvasDrop.ts.

import { IconButton, OverflowTooltip } from "@nustackdev/ui-kit";
import { X } from "lucide-react";
import { paneBar, paneBarTitle } from "../design";
import { PANE_MIME } from "../main/useCanvasDrop";
import type { PlaneMeta } from "../plane/types";
import { PaneMenu } from "./PaneMenu";

export function PaneBar({
	planeId,
	title,
	meta,
	onMeta,
	onDelete,
	onClose,
	first = true,
	movable = false,
	closable = true,
	lit = false,
}: {
	planeId: string;
	title: string;
	/** Null while the plane is loading. */
	meta: PlaneMeta | null;
	onMeta: (patch: Record<string, unknown>) => void;
	/** Left out for a Plane that cannot be deleted. */
	onDelete?: () => void;
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
			<OverflowTooltip label={title} side="right">
				<span className={paneBarTitle(lit)}>{title}</span>
			</OverflowTooltip>
			<PaneMenu planeId={planeId} meta={meta} onChange={onMeta} onDelete={onDelete} />
			{closable ? (
				<IconButton variant="ghost" size="sm" aria-label={`Close ${title}`} onClick={onClose}>
					<X />
				</IconButton>
			) : null}
		</header>
	);
}
