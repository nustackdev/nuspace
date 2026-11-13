// A plane's look: its title and its icon, for anything that names a plane
// it may not have open, a desk folder row first.
//
// One source: the desks node's titles, `set_titles` (./desks.ts), which
// covers every plane any desk links to, else "Untitled". Never a pane's own
// node, nor the sidebar's tree: what draws a desk folder reads the desks'
// data and nothing else.
//
// The browser tab names only the focused pane, from that pane's head
// (../shell/tab.ts).

import { useMemo } from "react";
import { type PlaneLook, useDeskTitles } from "./desks";

export type { PlaneLook };

/** What a plane is called with no title anywhere. */
export const UNTITLED = "Untitled";

/** The look of each of `planes`, off the desks' titles. */
export function usePlaneLooks(planes: string[]): Record<string, PlaneLook> {
	const titles = useDeskTitles();
	return useMemo(
		() =>
			Object.fromEntries(
				planes.map((id) => {
					const look = titles[id];
					return [id, { title: look?.title || UNTITLED, icon: look?.icon ?? "" }];
				}),
			),
		[planes, titles],
	);
}

/** Plane `plane`'s look in `looks`, "Untitled" with no icon when it has none. */
export function lookOf(looks: Record<string, PlaneLook>, plane: string): PlaneLook {
	return looks[plane] ?? { title: UNTITLED, icon: "" };
}
