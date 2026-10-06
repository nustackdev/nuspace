// The heading over the tree, and the one way to make a plane at the top
// level: `+` beside it, as each row's `+` makes one inside that row. It sits
// over the scrolling body, not in it, so it stays at hand however far the
// tree scrolls.

import { IconButton, Shortcut, Tooltip, TooltipContent, TooltipTrigger } from "@nustackdev/ui-kit";
import { Plus } from "lucide-react";
import { railAction, railSection, railSectionLabel, railTooltipHint } from "../design";
import { NEW_PLANE_KEYS, openAddPlane } from "./add";
import { ROOT_ID } from "./types";

export function PlanesHeader() {
	return (
		<div className={railSection}>
			<span className={railSectionLabel}>Planes</span>
			<Tooltip>
				<TooltipTrigger asChild>
					<IconButton
						variant="ghost"
						size="sm"
						ring="inset"
						aria-label="New plane"
						onClick={() => openAddPlane({ parent: ROOT_ID })}
						className={railAction}
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
