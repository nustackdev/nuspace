// The desk header: the row across the canvas's top while the tab is on a
// desk (an empty desk or one of its items). A solo plane has none.
//
// Only the desk's icon and name, and close right beside them. The desk's
// items are the sidebar's, never listed here too: the sidebar is the one
// place to switch, drag, reset and close them (../sidebar/DeskRows.tsx).
//
// Close leaves the desk and keeps it: the tab goes to "/", which lands on
// home. Rename and delete are the desk folder's in the sidebar
// (../sidebar/DeskFolder.tsx).

import { IconButton, OverflowTooltip } from "@nustackdev/ui-kit";
import { LayoutGrid, X } from "lucide-react";
import { leaveDesk } from "../core/router";
import { deskHeader, deskHeaderIcon, deskHeaderName } from "../design";
import type { Desk } from "../desk/model";
import { deskLabel } from "../sidebar/api";

export function DeskHeader({
	deskId,
	desk,
}: {
	deskId: string;
	/** The desk as the router has it; null before it lands. */
	desk: Desk | null;
}) {
	const name = deskLabel(desk?.name ?? "");
	return (
		<header className={deskHeader} data-desk-header={deskId}>
			<LayoutGrid aria-hidden className={deskHeaderIcon} />
			<OverflowTooltip label={name} side="bottom">
				<span className={deskHeaderName}>{name}</span>
			</OverflowTooltip>
			<IconButton
				variant="ghost"
				size="xs"
				aria-label={`Close ${name}`}
				tip="Close desk"
				onClick={leaveDesk}
			>
				<X />
			</IconButton>
		</header>
	);
}
