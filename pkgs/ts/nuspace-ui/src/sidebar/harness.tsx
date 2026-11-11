// Tests only: the sidebar body's one focus around a section rendered on its
// own, the way ./Sidebar.tsx gives it to every section.

import type * as React from "react";
import { SidebarFocusContext, useSidebarFocus } from "./focus";

export function SidebarBody({
	keys,
	selected = null,
	children,
}: {
	/** The rows' keys, in the order they are drawn. */
	keys: string[];
	selected?: string | null;
	children: React.ReactNode;
}) {
	const focus = useSidebarFocus(keys, selected);
	return (
		<SidebarFocusContext value={focus}>
			{/* biome-ignore lint/a11y/noStaticElementInteractions: the body as ./Sidebar.tsx draws it */}
			<div
				ref={focus.containerRef}
				tabIndex={-1}
				onClick={focus.onClick}
				onKeyDown={focus.onKeyDown}
			>
				{children}
			</div>
		</SidebarFocusContext>
	);
}
