// The rail's top bar: collapse, the wordmark, and a `+` on the right that
// opens the Add plane popup for a top-level plane, the same as the New plane
// row under the Planes header (./NewPlaneRow.tsx) and cmd/ctrl+alt+N. Home,
// search and settings are the nav rows under it (./NavRows.tsx).

import {
	cn,
	IconButton,
	Shortcut,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { PanelLeft, Plus } from "lucide-react";
import {
	railChromeButton,
	railHeader,
	railHeaderEnd,
	railTooltipHint,
	railWordmark,
	railWordmarkNu,
} from "../design";
import { NEW_PLANE_KEYS, openAddPlane } from "./add";
import { focusRailToggle, RAIL_KEYS, setRailCollapsed } from "./collapse";
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
			<Tooltip>
				<TooltipTrigger asChild>
					<IconButton
						variant="ghost"
						size="sm"
						ring="inset"
						aria-label="New plane"
						onClick={() => openAddPlane({ parent: ROOT_ID })}
						className={cn(railChromeButton, railHeaderEnd)}
					>
						<Plus />
					</IconButton>
				</TooltipTrigger>
				<TooltipContent side="bottom">
					New plane
					<Shortcut keys={NEW_PLANE_KEYS} size="sm" className={railTooltipHint} />
				</TooltipContent>
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
