// The action row: "New plane", every "New ..." the sidebar offers, all
// alike. The one row (./SidebarRow.tsx) as a button: an icon (a `+` unless
// given), the label, and its shortcut when it has one.

import { type LucideIcon, Plus } from "lucide-react";
import type * as React from "react";
import { sidebarIcon } from "../design";
import { SidebarRow } from "./SidebarRow";

export function ActionRow({
	rowKey,
	label,
	icon: Icon = Plus,
	keys,
	onClick,
	drag,
	className,
}: {
	/** What the body's focus addresses it by. */
	rowKey: string;
	label: string;
	icon?: LucideIcon;
	/** Its shortcut by key name, shown at the row's end. */
	keys?: readonly string[];
	onClick: () => void;
	/** Drop handlers, for a row that takes drops too (an empty desk's). */
	drag?: React.ComponentProps<typeof SidebarRow>["drag"];
	/** A class on top of the row's own (a drop ring). */
	className?: string;
}) {
	return (
		<SidebarRow
			rowKey={rowKey}
			icon={<Icon aria-hidden="true" className={sidebarIcon(false)} />}
			label={label}
			trailing={keys ? { shortcut: keys } : undefined}
			onClick={onClick}
			drag={drag}
			className={className}
		/>
	);
}
