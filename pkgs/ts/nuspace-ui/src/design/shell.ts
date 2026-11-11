// Shell class recipes.
//
// The shell is the frame the two regions hang inside: the sidebar on the left,
// the desk area (the canvas) claiming the rest, both on one ground. It owns only the frame:
// how the window splits, the gaps, and the frame around each pane.
//
// The window has no chrome of its own. The connection dot and the theme flip
// sit in the sidebar footer. The one exception is the button that brings a
// collapsed sidebar back, which has nowhere else to be.
//
// Afterglow (the kit's `accent`) shows only as a line, or a ring on an empty
// desk: on a drop target and on a resize edge that is hovered or dragged.
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
 * The kit split handle between the sidebar and the desk area: the 6px gap
 * itself, no fill. The kit's own line shows on hover and while dragging.
 */
export const shellSplitHandle = "w-1.5 bg-transparent";

/**
 * Everything right of the sidebar. `group/main` with `data-sidebar="collapsed"`
 * while the sidebar is hidden, so the first pane header can make room for
 * the reopen button (see `paneHeader`).
 */
export const shellMain = "group/main relative flex min-h-0 min-w-0 flex-1";

/* ============================== The desk ================================= */

/**
 * The desk area: 6px from the window's top, right and bottom edges. The 6px
 * on the left is the sidebar's split handle.
 */
export const deskArea = "relative flex min-h-0 min-w-0 flex-1 py-1.5 pr-1.5";

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
 * The columns, side by side, 6px apart, then the end zone. Nothing shrinks to
 * fit: the row scrolls instead. At least as wide as the viewport, so the end
 * zone takes the room the columns leave.
 */
export const deskColumns = "flex h-full gap-1.5";

/**
 * The end zone after the last column: a drop here is a new column at the end.
 * It fills the room the columns leave and is nothing once they fill the row:
 * no strip ends in empty space (a drop on the last pane's right edge is a new
 * column at the end too). Its negative margin takes back the row's gap. Empty:
 * its drop line on its left edge is all it ever shows.
 */
export const deskEnd = "relative -ml-1.5 h-full min-w-0 flex-1";

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
 * One column: its panes stacked, 6px apart. Its width is set inline. The
 * column resize handle sits on its right edge.
 */
export const deskColumn = "relative flex h-full shrink-0 flex-col gap-1.5";

/**
 * A pane's place in its column: its share of the height, set inline as flex
 * grow. Holds the pane's drop line and the share resize handle under it.
 */
export const deskShare = "relative flex min-h-0 basis-0";

/**
 * A column's resize handle: the 6px gap on its right, the kit's split handle
 * with no hairline, so nothing shows until it is hovered, then the kit's 2px
 * afterglow line, which stays while dragging (`data-dragging`). The end zone
 * follows the last column, so its gap is there too.
 */
export function deskColumnHandle(last: boolean): string {
	return cn(
		splitHandleClasses("horizontal"),
		"absolute inset-y-0 w-1.5 bg-transparent",
		// In the gap to the next column; the last column has no gap after it
		// (the row ends at its edge), so its handle sits just inside it.
		last ? "right-0" : "-right-1.5",
	);
}

/** The share resize handle: the 6px gap under a pane, the same look as the column's. */
export const deskShareHandle = cn(
	splitHandleClasses("vertical"),
	"absolute inset-x-0 -bottom-1.5 h-1.5 bg-transparent",
);

/**
 * Where a drag would land: a 2px afterglow line on a pane's edge (a new
 * column there, or a strip made with a plane item) or on its top or bottom
 * (stacked there), or on the end zone's left edge (a new column at the end).
 */
export function deskDropLine(edge: "left" | "right" | "top" | "bottom"): string {
	return cn(
		"pointer-events-none absolute z-20 rounded-full bg-accent",
		edge === "left" && "inset-y-0 left-0 w-0.5",
		edge === "right" && "inset-y-0 right-0 w-0.5",
		edge === "top" && "inset-x-0 top-0 h-0.5",
		edge === "bottom" && "inset-x-0 bottom-0 h-0.5",
	);
}

/**
 * The one pane of a solo plane or a plane item: the whole desk area. Holds a
 * plane item's drop line.
 */
export const deskSolo = "relative flex min-h-0 min-w-0 flex-1";

/** An empty desk: the kit's `EmptyState`, filling the desk area. */
export const deskEmpty = "min-h-0 flex-1";

/**
 * A drag over an empty desk: a 2px afterglow ring inside the desk area's
 * edges, 8px radius like a pane.
 */
export const deskEmptyAim =
	"pointer-events-none absolute top-1.5 right-1.5 bottom-1.5 left-0 rounded-lg ring-2 ring-accent ring-inset";

/**
 * One pane on the canvas: 8px radius, a `line-subtle` border, the
 * `ground-raised` fill. Focus is in the header's title, never on the border.
 */
export const shellPane = cn(
	"group/pane relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden",
	"rounded-lg border border-border-subtle bg-nuspace-page",
	"outline-none",
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
