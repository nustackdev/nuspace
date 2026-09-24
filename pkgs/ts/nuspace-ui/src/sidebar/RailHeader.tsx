// The rail's top bar: collapse and the wordmark on the left, a new plane at
// the top level on the right, and room in between for search.
//
// No way home up here: home is an ordinary row in the tree.

import { IconButton, Tooltip, TooltipContent, TooltipTrigger } from "@nustackdev/ui-kit";
import { PanelLeft, SquarePen } from "lucide-react";
import {
	railChromeButton,
	railHeader,
	railHeaderSpace,
	railTooltipHint,
	railWordmark,
	railWordmarkNu,
} from "../design";
import { openAddPlane } from "./add";
import { focusRailToggle, RAIL_SHORTCUT, setRailCollapsed } from "./collapse";
import { ROOT_ID } from "./types";

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
			<div className={railHeaderSpace} />
			<Tooltip>
				<TooltipTrigger asChild>
					<IconButton
						variant="ghost"
						size="sm"
						aria-label="New plane"
						onClick={() => openAddPlane({ parent: ROOT_ID })}
						className={railChromeButton}
					>
						<SquarePen />
					</IconButton>
				</TooltipTrigger>
				<TooltipContent side="bottom">New plane</TooltipContent>
			</Tooltip>
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
				<span className={railTooltipHint}>{RAIL_SHORTCUT}</span>
			</TooltipContent>
		</Tooltip>
	);
}
