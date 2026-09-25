// The bar across a pane's top: the plane's title, its settings, and close.
// Only over a lone pane; a split gets the tab bar (../main/TabBar.tsx).
//
// Outside the plane's scroll, so it stays put while the plane moves under it.

import { IconButton, OverflowTooltip } from "@nustackdev/ui-kit";
import { X } from "lucide-react";
import { paneBar, paneBarTitle } from "../design";
import type { PlaneMeta } from "../plane/types";
import { PaneMenu } from "./PaneMenu";

export function PaneBar({
	planeId,
	title,
	meta,
	onMeta,
	onDelete,
	onClose,
}: {
	planeId: string;
	title: string;
	/** Null while the plane is loading. */
	meta: PlaneMeta | null;
	onMeta: (patch: Record<string, unknown>) => void;
	/** Left out for a Plane that cannot be deleted. */
	onDelete?: () => void;
	onClose: () => void;
}) {
	return (
		<header className={paneBar}>
			<OverflowTooltip label={title} side="right">
				<span className={paneBarTitle}>{title}</span>
			</OverflowTooltip>
			<PaneMenu planeId={planeId} meta={meta} onChange={onMeta} onDelete={onDelete} />
			<IconButton variant="ghost" size="sm" aria-label={`Close ${title}`} onClick={onClose}>
				<X />
			</IconButton>
		</header>
	);
}
