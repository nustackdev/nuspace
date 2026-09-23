// The rail's header strip: what this whole rail is.
//
// Fixed, above the scroll, and it carries no add button: what a + makes
// depends on which section it was pressed under, so every + is on a section
// row and there is no such thing as adding to the rail itself.

import { railHeader, railHeaderLabel } from "../../design";

export function RailHeader({ label }: { label: string }) {
	return (
		<div className={railHeader}>
			<span className={railHeaderLabel}>{label}</span>
		</div>
	);
}
