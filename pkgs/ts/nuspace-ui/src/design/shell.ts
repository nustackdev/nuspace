// Shell class recipes.
//
// The shell is the frame the two regions hang inside: the sidebar on the left,
// the Viewer claiming the rest. It owns only the frame - how the window splits
// and how each side claims its share.
//
// The window has no chrome of its own at all. The connection pill and the theme
// flip are the only two controls left and they sit in the rail's footer: they
// used to float over the canvas, which is two controls with nothing holding
// them, and the rail already has an edge for them.
//
// Everything resolves to kit L2/L4 semantic names. No raw hex, nothing off the
// 4px grid.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §1 grid, §4 row heights
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers

import { cn } from "@nustackdev/ui-kit";

/* ============================== the frame ================================ */

/** The window. Owns the viewport height so every region inside can go flex. */
export const shellRoot = "flex h-screen bg-bg-canvas text-text-primary";

/** Everything beside the sidebar. */
export const shellMain = "flex min-h-0 min-w-0 flex-1";

/**
 * A full-bleed region. `min-w-0` so a wide child scrolls inside itself instead
 * of pushing the window sideways.
 *
 * Used twice, deliberately the same box: the shell's slot, and the region's own
 * root.
 */
export const shellSurface = "flex min-h-0 min-w-0 flex-1";

/* ============================== panes ==================================== */

/** The Viewer's row of panes. Equal shares, each one its own scroll host. */
export const shellPanes = "flex min-h-0 min-w-0 flex-1";

/**
 * One pane. `basis-0` + `flex-1` is what makes the shares equal whatever each
 * holds; `min-w-0` lets a wide block scroll inside its pane instead of
 * pushing the neighbour out. Every pane after the first draws the hairline
 * divider on its left edge.
 */
export function shellPane(divided: boolean): string {
	return cn(
		"group/pane relative flex min-h-0 min-w-0 flex-1 basis-0",
		divided && "border-l border-border-subtle",
	);
}

/**
 * The focus mark: a 2px line across the top of the focused pane. Only drawn
 * with more than one pane, so a single pane looks exactly as it always did.
 */
export function shellPaneFocusLine(focused: boolean): string {
	return cn(
		"pointer-events-none absolute inset-x-0 top-0 z-20 h-0.5",
		"transition-colors duration-fast ease-out",
		focused ? "bg-doc-selected-line" : "bg-transparent",
	);
}

/**
 * The pane's close button, top right. Hover-revealed on a lone pane so the
 * page reads as it always did; always there, quietly, once there is a split.
 */
export function shellPaneClose(split: boolean): string {
	return cn(
		"absolute top-2 right-3 z-20 text-text-muted",
		"transition-opacity duration-fast ease-out",
		split
			? "opacity-60 hover:opacity-100 focus-visible:opacity-100"
			: "opacity-0 group-hover/pane:opacity-100 focus-visible:opacity-100",
	);
}

/* ============================== states =================================== */

/** Before the first write lands. Centred, quiet, the whole window. */
export const shellBooting = cn(
	"flex min-h-screen items-center justify-center gap-2",
	"bg-bg-canvas text-base text-text-muted",
);

/** A region the tree does not hold. A fact, not an error, so no tone. */
export const shellMissing = "min-h-0 flex-1 p-6 text-base text-text-muted";
