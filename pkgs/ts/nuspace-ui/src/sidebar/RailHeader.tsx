// The rail's header strip: what this whole rail is, and the way home.
//
// Fixed, above the scroll, and it carries no add button: what a + makes
// depends on which section it was pressed under, so every + is on a section
// row and there is no such thing as adding to the rail itself.
//
// The wordmark is an anchor to "/", the home Plane: home is listed under no
// section, so this is its row. A plain click goes home, alone in one pane;
// cmd/ctrl-click opens it as a split, like any row.

import { HOME, hrefFor, onHomeClick, useFocusedRoute } from "../app/router";
import { railHeader, railHeaderLabel } from "../design";

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
		</div>
	);
}
