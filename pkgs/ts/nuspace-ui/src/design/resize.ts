// The column resize handle, shared by the rail's edge and the borders between
// panes, so every draggable edge in the window looks and behaves the same.

import { cn } from "@nustackdev/ui-kit";

/**
 * An 8px drag strip centred on a hairline, so it is easy to hit without
 * eating the content on either side. A 2px accent line fades in on hover and
 * while dragging. `side` is which edge of the positioned parent it rides.
 */
export function resizeHandle(side: "left" | "right"): string {
	return cn(
		"group/resize absolute inset-y-0 z-30 w-2 cursor-col-resize touch-none",
		side === "left" ? "-left-1" : "-right-1",
		"after:absolute after:inset-y-0 after:left-1/2 after:w-0.5 after:-translate-x-1/2",
		"after:bg-accent after:opacity-0 after:transition-opacity after:duration-fast",
		"hover:after:opacity-60 active:after:opacity-100",
	);
}
