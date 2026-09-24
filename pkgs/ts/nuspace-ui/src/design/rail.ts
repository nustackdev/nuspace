// Rail class recipes + geometry. The sidebar's whole vocabulary.
//
// The rail is the one place in nuspace where three things share a 28px line
// - a disclosure lane, a truncating label, and a hover-revealed action lane -
// and every "it feels off" bug in the rail traced back to those three lanes
// being positioned against each other by hand instead of by a stated geometry.
//
// So the geometry is stated once, here, and the row is laid out in normal flow
// against it. No absolute positioning, no magic offsets, nothing that can drift
// into the title.
//
// The row's left inset is carried by the `inset` argument on `railRow` /
// `railSkeletonRow`. A tree row gets its left offset from `railIndent(depth)`;
// a flat row has no indent to stand in for it and pays for the inset itself.
//
// Everything resolves to kit L2/L4 semantic names or the doc-* names in
// ./tokens.css. No raw hex, nothing off the 4px grid.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §4 row heights, §1 grid
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers, §2.4 wash
//   go/projects/nustackdev/design/motion.md         §3 nav rows
//   go/projects/nustackdev/design/a11y.md           §4 aria, §5 focus ring

import { cn } from "@nustackdev/ui-kit";
import { resizeHandle } from "./resize";

/* ============================== Geometry ================================= */

/**
 * The three lanes of a row, in px, all on the 4px grid.
 *
 * ```
 *  |<- depth*INDENT ->|<- LANE ->|<- GAP ->| title ...       |<- ACTIONS ->|
 *  |                  | chevron  |         | truncates       | +   ...     |
 * ```
 *
 * `LANE` and `GAP` are why the twisty used to sit on top of the first letter:
 * the old row put the chevron at `depth*12 + 2` with a 20px box and started the
 * title at `depth*12 + 20`, so the box overhung the text by 2px and the glyph
 * itself landed a pixel into it. Stating the lanes and laying them out in flow
 * makes that class of bug unrepresentable.
 */
export const RAIL = {
	/** Indent per tree level. 12 = spacing 3. */
	INDENT: 12,
	/** Disclosure / page-icon lane. 20 = a `sm` IconButton shrunk to the row. */
	LANE: 20,
	/** Lane-to-title gap. 4 = spacing 1. */
	GAP: 4,
	/** Row height. 28 = space-radius.md's "dense list row". */
	ROW: 28,
} as const;

/** Left inset for a row at `depth`, as an inline style (depth is data). */
export function railIndent(depth: number): { paddingLeft: string } {
	return { paddingLeft: `${depth * RAIL.INDENT}px` };
}

/* ============================== The aside =============================== */

/** Rail width bounds, px. DEFAULT is the old fixed w-60. */
export const RAIL_WIDTH = { MIN: 180, DEFAULT: 240, MAX: 480 } as const;

/**
 * The rail itself. Its own surface, hairline edge. The width is inline (the
 * user drags it, see sidebar/useRailWidth.ts), so none is set here.
 */
export const railAside = cn(
	"relative flex shrink-0 flex-col",
	"border-r border-border-subtle bg-bg-surface",
);

/** The drag strip on the rail's right edge. See ./resize.ts. */
export const railResizeHandle = resizeHandle("right");

/** Header strip. `h-chrome`, like the pane bar and the tab bar, so the rules line up. */
export const railHeader = cn(
	"flex h-chrome shrink-0 items-center gap-1",
	"border-b border-border-subtle pl-3 pr-1.5",
);

export const railHeaderLabel = cn(
	"flex-1 select-none text-xs font-medium uppercase tracking-[0.06em]",
	"text-text-muted no-underline hover:text-text-primary aria-[current=page]:text-text-primary",
);

/**
 * Footer strip. The window's own chrome, which used to float in the bottom
 * right corner of the canvas: a connection pill and a theme flip sitting over
 * a document are two controls with nothing holding them, and the rail already
 * has an edge to put them on.
 */
export const railFooter = cn(
	"flex h-chrome shrink-0 items-center justify-between gap-1",
	"border-t border-border-subtle pl-3 pr-1.5",
);

/** Scroll body. `px-1.5` keeps a row's wash off the rail's own border. */
export const railScroll = "min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-1.5 py-1";

/**
 * A section's own title, on the row shell every other row uses. One tier back
 * and cased like the header strip, so a section reads as a label with rows
 * under it rather than as the first row of the list.
 */
export const railSectionTitle = cn(
	"min-w-0 flex-1 select-none truncate",
	"text-xs font-medium uppercase tracking-[0.06em] text-text-muted",
);

/* ============================== The row ================================= */

/**
 * The row shell. This is what paints hover and selection, not the link inside
 * it, so the wash spans the whole line including the disclosure and the action
 * lane. A wash that stops short of the controls sitting on it reads as two
 * elements, which is most of what "a bit off" was.
 *
 * Hover is neutral (`doc-hover`), selection is accent (`doc-selected`). The kit
 * only has `accent-wash` and uses it for both, which makes a hovered row
 * indistinguishable from the open one - see tokens.css.
 *
 * With a split open, every open Plane's row is washed and the focused pane's
 * row is washed strongest.
 *
 * `inset` pads the row's own left edge. A tree row leaves it off because
 * `railIndent(depth)` already supplies the offset; a flat row turns it on.
 */
export function railRow(selected: boolean, inset = false, open = false): string {
	return cn(
		"group/row relative flex items-center rounded-md",
		"h-7 pr-1",
		inset && "pl-1.5",
		"transition-colors duration-fast ease-out",
		// The row is the tree item, so the row carries the focus ring. Offset 0:
		// the kit's 2px offset gets clipped by the rail's own overflow.
		"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-0",
		// `open` is a Plane showing in a pane that is not the focused one: the
		// same accent, half the wash, so the focused row stays the strongest.
		selected
			? "bg-doc-selected"
			: open
				? "bg-doc-selected/50"
				: "hover:bg-doc-hover active:bg-doc-active",
	);
}

/**
 * The disclosure / page-icon lane. Fixed width whether or not it holds a
 * control, which is what keeps titles at every depth on one left edge.
 */
export const railLane = "flex shrink-0 items-center justify-center";

export const railLaneStyle = { width: `${RAIL.LANE}px`, marginRight: `${RAIL.GAP}px` };

/**
 * The twisty, on top of a kit `IconButton ghost`. Shrunk to the lane and
 * re-tinted: `ghost` hovers to `bg-elevated`, which inside an already-washed
 * row reads as a separate chip stuck to the label.
 */
export const railTwisty = cn(
	"size-5 rounded-sm text-text-muted",
	"hover:bg-doc-active hover:text-text-primary",
	"focus-visible:ring-offset-0",
	"[&_svg]:size-3.5",
);

/** Leaf marker. Not a control, so it is not a button and takes no hit area. */
export const railLeafIcon = cn(
	"size-3.5 shrink-0 text-text-muted/70",
	"transition-colors duration-fast ease-out",
);

/**
 * The label, on top of a kit `NavLink`. NavLink stays because it is a real
 * anchor (cmd-click, middle-click, `aria-current="page"` for free) and it owns
 * the text tiers. What it does not own here is the background: the row shell
 * paints that, so both of NavLink's washes are zeroed out.
 *
 * `ring-offset-0` because the kit's 2px focus offset gets clipped by the
 * rail's own overflow.
 */
export const railLabel = cn(
	"h-full min-w-0 flex-1 gap-0 px-0",
	"bg-transparent hover:bg-transparent",
	"aria-[current=page]:bg-transparent data-[active=true]:bg-transparent",
	"focus-visible:ring-offset-0",
);

export const railTitle = "min-w-0 flex-1 truncate";

/** Placeholder for a row with no name yet. One tier back, never italic. */
export const railTitleEmpty = cn(railTitle, "text-text-muted");

/**
 * The action lane. Always in flow and always the same width, so the title
 * truncates against a stable edge and nothing reflows on hover; only the
 * opacity moves. Hidden controls are also click-through, because an invisible
 * button that still eats a click is worse than no button.
 */
export const railActions = cn(
	"flex shrink-0 items-center gap-0.5",
	"pointer-events-none opacity-0",
	"transition-opacity duration-fast ease-out",
	"group-hover/row:pointer-events-auto group-hover/row:opacity-100",
	"group-focus-within/row:pointer-events-auto group-focus-within/row:opacity-100",
	// Keep them up while a menu they opened is still open
	"[&:has([data-state=open])]:pointer-events-auto [&:has([data-state=open])]:opacity-100",
);

/** Same shrink + re-tint as the twisty, for the two action buttons. */
export const railAction = cn(
	"size-5 rounded-sm",
	"hover:bg-doc-active hover:text-text-primary",
	"focus-visible:ring-offset-0",
	"[&_svg]:size-3.5",
);

/**
 * Wrapper that puts the indent guides *behind* the row. Both interaction
 * washes are translucent color-mixes, so a guide under a hovered or open row
 * stays legible but drops back a tier instead of scratching across it.
 */
export const railRowWrap = "relative";

/**
 * Indent guide. One hairline per crossed level, drawn down the middle of that
 * level's disclosure lane so it lines up with the ancestor chevrons it belongs
 * to. IDE trees (VSCode, Fleet) all carry these; three levels into a 240px
 * rail, indent alone stops being readable.
 */
export const railGuide = "pointer-events-none absolute inset-y-0 w-px bg-border-subtle";

export function railGuideStyle(level: number): { left: string } {
	return { left: `${level * RAIL.INDENT + Math.floor(RAIL.LANE / 2)}px` };
}

/* ============================== Inline edit ============================= */

/**
 * Rename and create both happen in place, in the row, on top of a kit `Input`
 * shrunk to the row. The rail used to reach for `window.prompt`, which blocks
 * the whole tab, cannot be styled, cannot be themed, and drops you out of the
 * document you were reading. It is not a dialog, it is an absence of one.
 */
export const railInputBox = "flex min-w-0 flex-1 items-center";

export const railInput = cn("h-6 min-w-0 flex-1 px-1 py-0 text-sm", "focus-visible:ring-offset-0");

/* ============================== Empty + loading ========================= */

/** Row-shaped placeholder, so the rail does not resize when the list lands. */
export function railSkeletonRow(inset = false): string {
	return cn("flex h-7 items-center", inset ? "px-1.5" : "pr-1");
}

/** The bar inside a skeleton row, on top of a kit `Skeleton`. */
export const railSkeletonBar = "h-3 w-full rounded-sm";

export const railEmpty = cn("select-none px-2 py-3 text-sm text-text-muted");
