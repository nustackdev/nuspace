// New plane, at the top level: the tree's first row, shaped like the rows
// under it, as each row's `+` makes one inside that row. Sticky, so it stays
// at hand however far the tree scrolls.

import { Shortcut } from "@nustackdev/ui-kit";
import { Plus } from "lucide-react";
import {
	railLane,
	railNewPlane,
	railNewPlaneBar,
	railNewPlaneIcon,
	railNewPlaneKeys,
	railNewPlaneLabel,
} from "../design";
import { NEW_PLANE_KEYS, openAddPlane } from "./add";
import { ROOT_ID } from "./types";

export function NewPlaneRow() {
	return (
		<div className={railNewPlaneBar}>
			<button
				type="button"
				className={railNewPlane}
				onClick={() => openAddPlane({ parent: ROOT_ID })}
			>
				<span className={railLane}>
					<Plus aria-hidden="true" className={railNewPlaneIcon} />
				</span>
				<span className={railNewPlaneLabel}>New plane</span>
				<Shortcut keys={NEW_PLANE_KEYS} variant="ghost" size="sm" className={railNewPlaneKeys} />
			</button>
		</div>
	);
}
