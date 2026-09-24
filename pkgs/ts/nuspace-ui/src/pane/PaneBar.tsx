// The bar across a pane's top: the page's title, its settings, and close.
//
// Outside the page's scroll, so it stays put while the page moves under it.

import { IconButton } from "@nustackdev/ui-kit";
import { X } from "lucide-react";
import { paneBar, paneBarButton, paneBarTitle } from "../design";
import type { PageMeta } from "../page/types";
import { PaneMenu } from "./PaneMenu";

export function PaneBar({
	title,
	meta,
	strong,
	onMeta,
	onClose,
}: {
	title: string;
	/** Null while the page is loading. */
	meta: PageMeta | null;
	/** The focused pane of a split. */
	strong: boolean;
	onMeta: (patch: Record<string, unknown>) => void;
	onClose: () => void;
}) {
	return (
		<header className={paneBar}>
			<span className={paneBarTitle(strong)} title={title}>
				{title}
			</span>
			<PaneMenu meta={meta} onChange={onMeta} />
			<IconButton
				variant="ghost"
				size="sm"
				aria-label={`Close ${title}`}
				onClick={onClose}
				className={paneBarButton}
			>
				<X />
			</IconButton>
		</header>
	);
}
