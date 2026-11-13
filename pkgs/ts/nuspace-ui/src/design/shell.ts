// Shell class recipes.
//
// The shell is the frame the two regions hang inside: the sidebar on the left,
// the desk area (the canvas) claiming the rest, both on one ground. It owns only the frame:
// how the window splits, the gaps, and the frame around each pane.
//
// The window has no chrome of its own. The connection dot and the theme flip
// sit in the sidebar footer. Folded, the sidebar is its rail (./sidebar.ts).
//
// Afterglow (the kit's `accent`) shows only on a drop target, as the region
// the drop makes, and as a line on a resize edge that is hovered or dragged.
//
// Colors resolve to kit L2/L4 semantic names or the nuspace-* frame roles
// in ./theme.css. No raw hex. Spacing is the 4px grid, except the 6px gaps
// and desk edges the shell spec sets.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §1 grid, §4 row heights
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers

import { cn, splitHandleClasses } from "@nustackdev/ui-kit";
import { docPlaneSurface } from "./document";

/* ============================== The frame ================================ */

/**
 * The window: one canvas, `ground-deep` (the kit's `bg-sunken`) behind
 * everything, the sidebar and the desk alike. Owns the viewport height so
 * every region inside can go flex. Its one child is the kit split that puts
 * the sidebar and the desk area side by side (shell/Shell.tsx).
 */
export const shellRoot = "flex h-screen bg-bg-sunken text-text-primary";

/**
 * A kit split panel one region sits in: the sidebar, the desk area.
 * The kit sizes it; the region fills it.
 */
export const shellSlot = "flex min-h-0";

/**
 * The sidebar's split panel: a named group, because the kit sets its
 * `data-state` (expanded / collapsed) on every frame of a drag, so what the
 * panel shows follows the fold live and never lags a drag.
 */
export const shellSideSlot = cn(shellSlot, "group/side");

/** The open sidebar in its panel: gone while the panel is folded. */
export const shellSideOpen = "flex min-h-0 min-w-0 flex-1 group-data-[state=collapsed]/side:hidden";

/** The rail in the sidebar's panel: there only while the panel is folded. */
export const shellSideRail = "hidden min-h-0 flex-1 group-data-[state=collapsed]/side:flex";

/**
 * The kit split handle between the sidebar and the desk area, as the kit
 * draws it: a `line-subtle` hairline, the afterglow line on hover and while
 * dragging. The shell is flat, so this line is the sidebar's edge.
 */
export const shellSplitHandle = "";

/** Everything right of the sidebar. */
export const shellMain = "group/main relative flex min-h-0 min-w-0 flex-1";

/* ============================== The desk ================================= */

/**
 * The desk area: flat, edge to edge, the panes' own fill. No gaps, no
 * radius: panes meet on hairlines, and a pane cut by the window edge reads
 * like any app window, not a card sliced in half.
 */
export const deskArea = "relative flex min-h-0 min-w-0 flex-1 bg-nuspace-page";

/**
 * A strip's desk area: a size container, so a column's default width is a
 * part of the canvas in pure css (`deskColumnWidth`), nothing measured.
 */
export const deskStripArea = cn(deskArea, "@container");

/**
 * A strip's row: the kit's scroll area, sideways only, the desk area's full
 * height. Its viewport and content keep a plain flex and full height chain
 * (the kit's horizontal area makes its content a block as tall as the
 * viewport), so Firefox draws it the same as Chrome.
 */
export const deskRow = "min-h-0 min-w-0 flex-1";

/** A strip's row viewport: no wheel past its ends into the page. */
export const deskRowViewport = "overscroll-x-contain";

/**
 * The columns, side by side, edge to edge: the column handle on each one's
 * right is the hairline between them. Nothing shrinks to fit: the row
 * scrolls instead. Holds the drop region, so it scrolls with the columns.
 * A new column at the end is a drop on the last pane's right edge.
 */
export const deskColumns = "relative flex h-full";

/**
 * A column's width, as an inline style value: `null` for the canvas's full
 * width (a strip's only column), px when stored, else two thirds of the
 * canvas, so a second column shows beside the first.
 */
export function deskColumnWidth(px: number | null | undefined): string | number {
	if (px === null) return "100cqw";
	return px ?? "calc(100cqw * 2 / 3)";
}

/**
 * One column: its panes stacked edge to edge, the share handle between them
 * the hairline. Its width is set inline. The column resize handle sits on
 * its right edge.
 */
export const deskColumn = "relative flex h-full shrink-0 flex-col";

/**
 * A pane's place in its column: its share of the height, set inline as flex
 * grow. Holds the share resize handle under it.
 */
export const deskShare = "relative flex min-h-0 basis-0";

/**
 * A column's resize handle on its right edge: the kit's split handle, its
 * `line-subtle` hairline the line between this column and the next, the
 * kit's 2px afterglow line on hover and while dragging (`data-dragging`).
 */
export function deskColumnHandle(last: boolean): string {
	return cn(
		splitHandleClasses("horizontal"),
		"absolute inset-y-0",
		// On the seam to the next column; the last column's sits just inside
		// it, so the row never scrolls a pixel past its end.
		last ? "right-0" : "-right-px",
	);
}

/** The share resize handle: the hairline under a pane, the same look as the column's. */
export const deskShareHandle = cn(splitHandleClasses("vertical"), "absolute inset-x-0 -bottom-px");

/**
 * Where a drag would land, drawn as the region the drop makes: the half of a
 * column's full height for a new column beside it (every pane stacked in it),
 * the half of a pane for one stacked there or for a plane item made a strip.
 * A light Afterglow wash inside a 1.5px Afterglow line, square like a flat
 * pane, no elevation. Placed inline, on the region's own edges
 * (main/DropRegion.tsx).
 * Its label is the kit's Badge, centered.
 */
export const deskDropRegion = cn(
	"pointer-events-none absolute z-20 flex items-center justify-center",
	"bg-doc-drop ring-[1.5px] ring-doc-drop-line ring-inset",
);

/**
 * A target that takes no drop, drawn over the pane it points at: a light
 * neutral wash in a dashed muted line, its reason on an outline Badge.
 */
export const deskDropRefused = cn(
	"pointer-events-none absolute z-20 flex items-center justify-center",
	"bg-bg-hover outline-1 -outline-offset-1 outline-dashed outline-text-muted",
);

/**
 * The region gliding from one target to the next. Only once shown: a region
 * that appears is placed, not flown in.
 */
export const deskDropGlide =
	"transition-[left,top,width,height] duration-fast ease-out motion-reduce:transition-none";

/**
 * The one pane of a solo plane or a plane item: the whole desk area. Holds
 * its drop region.
 */
export const deskSolo = "relative flex min-h-0 min-w-0 flex-1";

/** An empty desk: the kit's `EmptyState`, filling the desk area. */
export const deskEmpty = "min-h-0 flex-1";

/**
 * A drag over an empty desk: the drop region over the whole desk, on the
 * desk area's edges, saying "Pin".
 */
export const deskEmptyAim = cn(deskDropRegion, "inset-0");

/**
 * One pane on the desk: flat, no border and no radius, the `ground-raised`
 * fill. The handles around it draw its edges. Focus is in the header's
 * title, never on an edge.
 *
 * A size container, both ways: the air under a plane's last cell is a third
 * of the pane's height (tokens.css `--spacing-doc-tail`).
 */
export const shellPane = cn(
	"group/pane [container-type:size] relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden",
	"bg-nuspace-page outline-none",
);

/**
 * The plane's scroll host for the viewer skeleton the shell draws while it
 * boots. A pane's own body is `paneBody`.
 */
export const shellPanePlane = cn(docPlaneSurface, "bg-transparent");

/* ============================== States =================================== */

/** A region the tree does not hold: the kit's `EmptyState`, filling the desk area. */
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
