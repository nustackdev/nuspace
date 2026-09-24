// Shell class recipes.
//
// The shell is the frame the two regions hang inside: the sidebar on the left,
// the Viewer claiming the rest. It owns only the frame - how the window splits
// and how each side claims its share.
//
// The window has no chrome of its own. The connection dot and the theme flip
// sit in the rail's bottom bar: they used to float over the canvas, which is
// two controls with nothing holding them, and the rail already has an edge for
// them. The one exception is the button that brings a collapsed rail back,
// which has nowhere else to be.
//
// Everything resolves to kit L2/L4 semantic names. No raw hex, nothing off the
// 4px grid.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §1 grid, §4 row heights
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers

import { cn } from "@nustackdev/ui-kit";
import { docPlaneSurface } from "./document";
import { resizeHandle } from "./resize";

/* ============================== The frame ================================ */

/** The window. Owns the viewport height so every region inside can go flex. */
export const shellRoot = "flex h-screen bg-bg-canvas text-text-primary";

/**
 * Everything beside the sidebar. `group/main` with `data-rail="collapsed"`
 * while the rail is hidden, so the bars along the top can make room for the
 * reopen button (see `paneBar`, `tabBar`).
 */
export const shellMain = "group/main relative flex min-h-0 min-w-0 flex-1";

/**
 * The reopen button's slot, over the top left corner of the main strip and
 * centred on the chrome line. Its glyph lands where the rail's collapse
 * button had it. The button is `railChromeButton`.
 */
export const shellRailOpen = "absolute top-0 left-rail-bar-pad z-20 flex h-chrome items-center";

/**
 * A full-bleed region. `min-w-0` so a wide child scrolls inside itself instead
 * of pushing the window sideways.
 */
export const shellSurface = "flex min-h-0 min-w-0 flex-1";

/* ============================== Panes ==================================== */

/**
 * A pane's narrowest, px: the plane's reading measure (`max-w-doc`, 40rem in
 * tokens.css), so a split never squeezes a plane under the width it is written
 * for. A number and not a class because the strip's resize math needs it too.
 */
export const PANE_MIN_WIDTH = 640;

/**
 * The Viewer: the tab bar (only with a split, see ./tabs.ts) over the strip
 * of panes.
 */
export const shellStrip = "flex min-h-0 min-w-0 flex-1 flex-col";

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
 * One pane: its top bar over its own scroll host. `min-w-0` lets a wide cell
 * scroll inside the pane instead of pushing the neighbour out; the share and
 * the split minimum are inline (see main/usePaneWidths.ts). Every pane after
 * the first draws the divider on its left edge, which is where the resize
 * handle sits.
 *
 * The pane paints its own background, and that is the focus mark: with a
 * split, every pane but the focused one sits a step down on `bg-sunken`, and
 * the focused one keeps the canvas, the same surface as its tab above it
 * (./tabs.ts). Only the surface dims, never the content, so text keeps its
 * contrast. A single pane is never dimmed and looks as it always did.
 * `duration-fast`; the kit's reduced-motion rule flattens it to instant.
 */
export function shellPane(divided: boolean, dimmed: boolean): string {
	return cn(
		"group/pane relative flex min-h-0 min-w-0 flex-col",
		"transition-colors duration-fast ease-out",
		dimmed ? "bg-bg-sunken" : "bg-bg-canvas",
		divided && "border-l border-border-default",
	);
}

/**
 * The plane's scroll host inside a pane. Transparent, so the pane's own
 * background (canvas, or sunken when dimmed) is the one that shows.
 */
export const shellPanePlane = cn(docPlaneSurface, "bg-transparent");

/**
 * The zero-width slot between two panes that holds their resize handle. In
 * flow so it sits exactly on the divider, zero-width so it takes no share.
 */
export const shellPaneDivider = "relative w-0 shrink-0";

/** The handle itself, centred on the divider. See ./resize.ts. */
export const shellPaneResize = resizeHandle("left");

/* ============================== States =================================== */

/** Before the first write lands. Centred, quiet, the whole window. */
export const shellBooting = cn(
	"flex min-h-screen items-center justify-center gap-2",
	"bg-bg-canvas text-base text-text-muted",
);

/** A region the tree does not hold. A fact, not an error, so no tone. */
export const shellMissing = "min-h-0 flex-1 p-6 text-base text-text-muted";
