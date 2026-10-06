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
// Colors resolve to kit L2/L4 semantic names or the nuspace-* frame roles
// in ./theme.css. No raw hex, nothing off the
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
export const shellRoot = "flex h-screen bg-nuspace-page text-text-primary";

/**
 * Everything beside the sidebar. `group/main` with `data-rail="collapsed"`
 * while the rail is hidden, so the bars along the top can make room for the
 * reopen button (see `paneBar`).
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
 * tokens.css), so the desk never squeezes a plane under the width it is written
 * for. A number and not a class because the strip's resize math needs it too.
 */
export const PANE_MIN_WIDTH = 640;

/**
 * The Viewer: the desk, a strip of panes, over the dock (only while the desk
 * scrolls, see ./dock.ts).
 */
export const shellStrip = "flex min-h-0 min-w-0 flex-1 flex-col";

/**
 * The desk: the Viewer's strip of panes. When the panes' minimums add up to
 * more than the window has, it scrolls sideways (trackpad, shift-wheel) with
 * no scrollbar drawn: the dock under it is its scrollbar.
 */
export const shellPanes = cn(
	"flex min-h-0 min-w-0 flex-1",
	"overflow-x-auto overflow-y-hidden overscroll-x-contain scrollbar-none",
);

/**
 * One pane: its top bar over its own scroll host. `min-w-0` lets a wide cell
 * scroll inside the pane instead of pushing the neighbour out; the share and
 * the desk minimum are inline (see main/usePaneWidths.ts). Every pane after
 * the first draws the divider on its left edge, which is where the resize
 * handle sits.
 *
 * The pane paints its own background, and that is the focus mark: with more
 * than one pane, every pane but the focused one sits a step down on `nuspace-pane-dim`,
 * and the focused one keeps the page. Only the surface dims, never the content, so text keeps its
 * contrast. A single pane is never dimmed and looks as it always did.
 * `duration-fast`; the kit's reduced-motion rule flattens it to instant.
 */
export function shellPane(divided: boolean, dimmed: boolean): string {
	return cn(
		"group/pane relative flex min-h-0 min-w-0 flex-col",
		"transition-colors duration-fast ease-out",
		dimmed ? "bg-nuspace-pane-dim" : "bg-nuspace-page",
		divided && "border-l border-nuspace-edge",
	);
}

/**
 * The plane's scroll host inside a pane. Transparent, so the pane's own
 * background (page, or pane-dim when dimmed) is the one that shows.
 */
export const shellPanePlane = cn(docPlaneSurface, "bg-transparent");

/**
 * The zero-width slot between two panes that holds their resize handle. In
 * flow so it sits exactly on the divider, zero-width so it takes no share.
 */
export const shellPaneDivider = "relative w-0 shrink-0";

/** The handle itself, centred on the divider. See ./resize.ts. */
export const shellPaneResize = resizeHandle("left");

/**
 * Where a plane dragged from the rail would open: the half of the pane it
 * lands beside, washed in the accent, with a line on the edge the new pane
 * goes in at. Over the plane, under nothing it would need to click.
 */
export function shellPaneDrop(edge: "before" | "after"): string {
	return cn(
		"pointer-events-none absolute inset-y-0 z-30 w-1/2 bg-accent-wash border-accent",
		edge === "before" ? "left-0 border-l-2" : "right-0 border-r-2",
	);
}

/* ============================== States =================================== */

/** A region the tree does not hold: the kit's `EmptyState`, filling the strip. */
export const shellMissing = "min-h-0 flex-1";

/* ========================== Keyboard shortcuts ========================== */

/*
 * The shortcuts sheet (../shell/KeysDialog.tsx): a kit `Dialog lg`, its groups
 * in two columns that never split a group, scrolling inside the dialog when
 * the window is short. A line is its action on the left in secondary text and
 * its keys on the right as kit `Shortcut` caps, "or" between alternatives.
 */

/** The dialog: its content scrolls, so the header stays put. */
export const keysDialog = "max-h-[85vh] grid-rows-[auto_minmax(0,1fr)]";

export const keysBody = "-mx-2 columns-1 gap-8 overflow-y-auto px-2 sm:columns-2";

/** One group: never split across the two columns. */
export const keysGroup = "mb-5 break-inside-avoid";

export const keysGroupTitle = "mb-1.5 text-xs font-medium text-text-muted";

export const keysRow = "flex min-h-7 items-center justify-between gap-4";

export const keysDoes = "min-w-0 truncate text-sm text-text-secondary";

export const keysKeys = "flex shrink-0 items-center gap-1.5";

export const keysOr = "text-xs text-text-muted";
