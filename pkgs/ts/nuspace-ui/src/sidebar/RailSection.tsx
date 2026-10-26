// A section header in the rail's body (Pinned, Planes, Extensions): a quiet label over
// the section's rows, and an optional action on the rows' right edge, shown
// while the header is hovered or holds the keyboard.

import { IconButton, Shortcut, Tooltip, TooltipContent, TooltipTrigger } from "@nustackdev/ui-kit";
import type { LucideIcon } from "lucide-react";
import { railSection, railSectionAction, railSectionLabel, railTooltipHint } from "../design";

export type SectionAction = {
	label: string;
	icon: LucideIcon;
	keys?: readonly string[];
	onClick: () => void;
};

export function RailSection({ label, action }: { label: string; action?: SectionAction }) {
	return (
		<div className={railSection}>
			<span className={railSectionLabel}>{label}</span>
			{action ? <SectionButton {...action} /> : null}
		</div>
	);
}

function SectionButton({ label, icon: Icon, keys, onClick }: SectionAction) {
	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<IconButton
					variant="ghost"
					size="sm"
					ring="inset"
					aria-label={label}
					onClick={onClick}
					className={railSectionAction}
				>
					<Icon />
				</IconButton>
			</TooltipTrigger>
			<TooltipContent side="bottom">
				{label}
				{keys ? <Shortcut keys={keys} size="sm" className={railTooltipHint} /> : null}
			</TooltipContent>
		</Tooltip>
	);
}
