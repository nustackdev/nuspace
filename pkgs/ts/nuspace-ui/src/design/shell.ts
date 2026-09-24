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
import { resizeHandle } from "./resize";

/* ============================== the frame ================================ */

/** The window. Owns the viewport height so every region inside can go flex. */
export const shellRoot = "flex h-screen bg-bg-canvas text-text-primary";

/** Everything beside the sidebar. */
export const shellMain = "flex min-h-0 min-w-0 flex-1";

/**
 * A full-bleed region. `min-w-0` so a wide child scrolls inside itself instead
 * of pushing the window sideways.
 */
export const shellSurface = "flex min-h-0 min-w-0 flex-1";

/* ============================== panes ==================================== */

/**
 * A pane's narrowest, px: the page's reading measure (`max-w-doc`, 40rem in
 * tokens.css), so a split never squeezes a page under the width it is written
 * for. A number and not a class because the strip's resize math needs it too.
 */
export const PANE_MIN_WIDTH = 640;

/**
 * The Viewer's strip of panes. When the panes' minimums add up to more than
 * the window has, it scrolls sideways (trackpad, shift-wheel) with no
 * scrollbar drawn: the panes' own borders already say there is more.
 */
export const shellPanes = cn(
	"flex min-h-0 min-w-0 flex-1",
	"overflow-x-auto overflow-y-hidden overscroll-x-contain",
	"[scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
);

/**
 * One pane: its top bar over its own scroll host. `min-w-0` lets a wide block
 * scroll inside the pane instead of pushing the neighbour out; the share and
 * the split minimum are inline (see main/usePaneWidths.ts). Every pane after
 * the first draws the divider on its left edge, which is where the resize
 * handle sits.
 */
export function shellPane(divided: boolean): string {
	return cn(
		"group/pane relative flex min-h-0 min-w-0 flex-col",
		divided && "border-l border-border-default",
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
 * The zero-width slot between two panes that holds their resize handle. In
 * flow so it sits exactly on the divider, zero-width so it takes no share.
 */
export const shellPaneDivider = "relative w-0 shrink-0";

/** The handle itself, centred on the divider. See ./resize.ts. */
export const shellPaneResize = resizeHandle("left");

/* ============================== states =================================== */

/** Before the first write lands. Centred, quiet, the whole window. */
export const shellBooting = cn(
	"flex min-h-screen items-center justify-center gap-2",
	"bg-bg-canvas text-base text-text-muted",
);

/** A region the tree does not hold. A fact, not an error, so no tone. */
export const shellMissing = "min-h-0 flex-1 p-6 text-base text-text-muted";
