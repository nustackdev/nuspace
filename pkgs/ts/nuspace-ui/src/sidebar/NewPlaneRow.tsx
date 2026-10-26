// New plane, at the top level: the tree's first row, under the Planes header,
// shaped like the rows under it, as each row's `+` makes one inside that row.

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
import { NEW_PLANE_KEY, useRailNav } from "./useRailFocus";

export function NewPlaneRow() {
	const { tabKey, setActiveKey, arrows } = useRailNav();
	return (
		<div className={railNewPlaneBar}>
			<button
				type="button"
				className={railNewPlane}
				data-rail-key={NEW_PLANE_KEY}
				tabIndex={tabKey === NEW_PLANE_KEY ? 0 : -1}
				onFocus={() => setActiveKey(NEW_PLANE_KEY)}
				onKeyDown={(e) => arrows(e, NEW_PLANE_KEY)}
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
