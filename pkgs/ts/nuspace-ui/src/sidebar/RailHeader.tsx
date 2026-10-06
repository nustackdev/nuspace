// The rail's top bar: collapse and the wordmark. A new plane is the tree's
// first row (./NewPlaneRow.tsx), next to what it makes.
//
// No way home up here: home is an ordinary row in the tree.

import { IconButton, Shortcut, Tooltip, TooltipContent, TooltipTrigger } from "@nustackdev/ui-kit";
import { PanelLeft } from "lucide-react";
import {
	railChromeButton,
	railHeader,
	railTooltipHint,
	railWordmark,
	railWordmarkNu,
} from "../design";
import { focusRailToggle, RAIL_KEYS, setRailCollapsed } from "./collapse";

export function RailHeader() {
	return (
		<div className={railHeader}>
			<RailToggle
				label="Hide sidebar"
				onClick={() => {
					setRailCollapsed(true);
					focusRailToggle();
				}}
			/>
			<span className={railWordmark}>
				<span className={railWordmarkNu}>nu</span>space
			</span>
		</div>
	);
}

/**
 * The `panel-left` button, in the rail's top bar and, while the rail is
 * collapsed, over the main strip's top left corner (../shell/Shell.tsx).
 */
export function RailToggle({ label, onClick }: { label: string; onClick: () => void }) {
	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<IconButton
					variant="ghost"
					size="sm"
					ring="inset"
					aria-label={label}
					data-rail-toggle=""
					onClick={onClick}
					className={railChromeButton}
				>
					<PanelLeft />
				</IconButton>
			</TooltipTrigger>
			<TooltipContent side="bottom">
				{label}
				<Shortcut keys={RAIL_KEYS} size="sm" className={railTooltipHint} />
			</TooltipContent>
		</Tooltip>
	);
}
