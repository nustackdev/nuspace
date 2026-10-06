// Dock class recipes: the bar under the desk, a scaled map of its panes.
//
// The desk scrolls sideways with no scrollbar drawn; the dock is its
// scrollbar. One chip per pane, as wide as its share of the desk, and a
// window over the chips marking the part that is on screen, which is also the
// grip that drags the desk. Chips on screen read in the primary tier, the rest
// stay muted. The window is neutral, not accent: the chips are the subject.
//
// `h-chrome` tall like every other strip of window chrome, on `bg-sunken`
// with a rule along its top, so it reads as chrome and not as a pane.
//
// Everything resolves to kit L2/L4 semantic names or the doc-* names in
// ./tokens.css. No raw hex, nothing off the 4px grid.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §1 grid, §2 radius
//   go/projects/nustackdev/design/palette.md        §2.1 surfaces, §2.2 text tiers
//   go/projects/nustackdev/design/motion.md         §3 hover, focus ring

import { cn } from "@nustackdev/ui-kit";

/** The bar: a strip of chrome holding the track. */
export const dock = cn(
	"flex h-chrome shrink-0 items-stretch bg-bg-sunken",
	"border-t border-border-default",
);

/** The track: the whole desk, scaled to the bar, edge to edge, no padding. */
export const dockTrack = "relative min-w-0 flex-1 select-none overflow-hidden";

/**
 * One pane's chip, placed and sized inline as its share of the desk, a
 * hairline between chips. On screen: primary; off it: muted, and hover brings
 * it up a tier. Dimmed while it is being dragged.
 */
export function dockChip(onScreen: boolean, dragging: boolean): string {
	return cn(
		"absolute inset-y-0 flex min-w-0 items-center overflow-hidden",
		"border-l border-border-default first:border-l-0",
		"transition-colors duration-fast ease-out",
		onScreen ? "text-text-primary" : "text-text-muted hover:bg-doc-hover hover:text-text-secondary",
		dragging && "opacity-50",
	);
}

/**
 * The chip's button: icon and title, filling the chip. The ring is inset,
 * because the track's overflow clips the kit's offset.
 */
export const dockChipTrigger = cn(
	"flex h-full min-w-0 flex-1 cursor-default items-center gap-1.5 pl-2 text-left text-xs",
	"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
);

export const dockChipIcon = "shrink-0";

export const dockChipTitle = "min-w-0 truncate";

/** Where a dragged pane lands: a thin accent line on one edge of a chip. */
export function dockDropLine(edge: "before" | "after"): string {
	return cn(
		"pointer-events-none absolute inset-y-1 z-30 w-0.5 rounded-full bg-accent",
		edge === "before" ? "left-0" : "right-0",
	);
}

/**
 * The window: what is on screen, placed and sized inline (inset by
 * `DOCK_WINDOW_GAP` on each side, so it floats over the chips). A translucent
 * wash, no outline, and the whole of it is the grip: it drags the desk, the
 * way a scrollbar's thumb does. Hover deepens the wash.
 */
export const DOCK_WINDOW_GAP = 4;

export const dockWindow = cn(
	"absolute inset-y-1 z-10 cursor-grab rounded-md bg-dock-window active:cursor-grabbing",
	"transition-colors duration-fast ease-out hover:bg-dock-window-hover",
);
