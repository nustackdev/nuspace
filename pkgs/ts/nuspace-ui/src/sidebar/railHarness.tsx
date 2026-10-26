// Tests only: the rail body's one focus around a section rendered on its own,
// the way ./Rail.tsx gives it to every section.

import type * as React from "react";
import { RailFocusContext, useRailFocus } from "./useRailFocus";

export function RailBody({
	keys,
	selected = null,
	children,
}: {
	/** The rows' keys, in the order they are drawn. */
	keys: string[];
	selected?: string | null;
	children: React.ReactNode;
}) {
	const focus = useRailFocus(keys, selected);
	return (
		<RailFocusContext value={focus}>
			{/* biome-ignore lint/a11y/noStaticElementInteractions: the body as ./Rail.tsx draws it */}
			<div
				ref={focus.containerRef}
				tabIndex={-1}
				onClick={focus.onClick}
				onKeyDown={focus.onKeyDown}
			>
				{children}
			</div>
		</RailFocusContext>
	);
}
