// The rail's header strip: what this rail lists, and the one button that adds
// to it. Both rails have exactly that, so it is stated once.

import { IconButton, Tooltip, TooltipContent, TooltipTrigger } from "@nustackdev/ui-kit";
import { Plus } from "lucide-react";
import { railHeader, railHeaderLabel } from "../../design";

export function RailHeader({
	label,
	addLabel,
	addTooltip,
	addDisabled,
	onAdd,
}: {
	/** The strip label, e.g. "pages". The recipe cases it. */
	label: string;
	/** Accessible name for the add button, e.g. "New app". */
	addLabel: string;
	/** The hint under it, e.g. "new app". */
	addTooltip: string;
	addDisabled: boolean;
	onAdd: () => void;
}) {
	return (
		<div className={railHeader}>
			<span className={railHeaderLabel}>{label}</span>
			<Tooltip>
				<TooltipTrigger asChild>
					<IconButton
						variant="ghost"
						size="sm"
						aria-label={addLabel}
						disabled={addDisabled}
						onClick={onAdd}
					>
						<Plus />
					</IconButton>
				</TooltipTrigger>
				<TooltipContent side="bottom">{addTooltip}</TooltipContent>
			</Tooltip>
		</div>
	);
}
