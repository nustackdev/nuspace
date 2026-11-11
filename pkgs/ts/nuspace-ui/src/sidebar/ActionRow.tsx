// The action row: "New plane", every "New ..." the sidebar offers, all
// alike. The one row (./SidebarRow.tsx) as a button: a `+`, the
// label, and its shortcut when it has one.

import { Plus } from "lucide-react";
import { SidebarRow } from "./SidebarRow";

export function ActionRow({
	rowKey,
	label,
	keys,
	onClick,
}: {
	/** What the body's focus addresses it by. */
	rowKey: string;
	label: string;
	/** Its shortcut by key name, shown at the row's end. */
	keys?: readonly string[];
	onClick: () => void;
}) {
	return (
		<SidebarRow
			rowKey={rowKey}
			icon={<Plus aria-hidden="true" />}
			label={label}
			trailing={keys ? { shortcut: keys } : undefined}
			onClick={onClick}
		/>
	);
}
