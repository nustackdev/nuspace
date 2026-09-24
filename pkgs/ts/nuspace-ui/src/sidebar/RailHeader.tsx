// The rail's header strip: what this whole rail is, the way home, and the `+`
// that adds a Plane at the top level.
//
// The wordmark is an anchor to "/", the home Plane. A plain click goes home,
// alone in one pane; cmd/ctrl-click opens it as a split, like any row.

import { IconButton } from "@nustackdev/ui-kit";
import { Plus } from "lucide-react";
import { HOME, hrefFor, onHomeClick, useFocusedRoute } from "../core/router";
import { railAction, railHeader, railHeaderLabel } from "../design";
import { openAddPlane } from "./add";
import { ROOT_ID } from "./types";

export function RailHeader({ label }: { label: string }) {
	const home = useFocusedRoute() === HOME;
	return (
		<div className={railHeader}>
			<a
				href={hrefFor(HOME)}
				onClick={onHomeClick}
				aria-current={home ? "page" : undefined}
				title="Home"
				className={railHeaderLabel}
			>
				{label}
			</a>
			<IconButton
				variant="ghost"
				size="sm"
				aria-label="Add plane"
				title="Add plane"
				onClick={() => openAddPlane({ parent: ROOT_ID })}
				className={railAction}
			>
				<Plus />
			</IconButton>
		</div>
	);
}
