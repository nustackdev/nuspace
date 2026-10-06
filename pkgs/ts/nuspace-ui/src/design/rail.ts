// Rail class recipes + geometry. The sidebar's whole vocabulary.
//
// The rail is the one place in nuspace where three things share a 28px line
// - an icon lane, a truncating label, and a hover-revealed action lane - and
// every "it feels off" bug in the rail traced back to those three lanes being
// positioned against each other by hand instead of by a stated geometry.
//
// So the geometry is stated once, here, and the row is laid out in normal flow
// against it. No absolute positioning, no magic offsets, nothing that can drift
// into the title.
//
// The look is Notion's sidebar: 14px labels in the secondary text tier, a
// plane icon on every row that turns into the fold chevron on hover, `+` and
// `...` only on hover, and a quiet gray fill for the open row. No accent hue
// anywhere in the tree: the rail is navigation, the accent belongs to the
// document.
//
// Every length is a `--rail-*` token in ./tokens.css, which is where to tune
// them; that file also states the one left edge and the one right edge the
// top bar, the rows and the bottom bar share. A tree row gets its left pad,
// plus its depth, from `railIndent(depth)`; a flat row has no indent and pays
// for the pad with the `inset` argument on `railRow` / `railSkeletonRow`.
//
// Everything resolves to kit L2/L4 semantic names or the doc-* and rail-*
// names in ./tokens.css. No raw hex, nothing off the 4px grid.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §4 row heights, §1 grid
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers, §2.4 wash
//   go/projects/nustackdev/design/motion.md         §3 nav rows
//   go/projects/nustackdev/design/a11y.md           §4 aria, §5 focus ring

import { cn } from "@nustackdev/ui-kit";
import { resizeHandle } from "./resize";

/* ============================== Geometry ================================= */

/*
 * The three lanes of a row. The lengths are tokens (tokens.css, `--rail-*`).
 *
 * ```
 *  |<- row-pad + depth*indent ->|<- lane ->|<- gap ->| title ... |<- actions ->|
 *  |                            | icon  or |         | truncates | +   ...     |
 *  |                            | chevron  |         |           |             |
 * ```
 *
 * The actions lane has that width only while revealed (see `railActions`); at
 * rest it is zero wide and the title runs to the row's end pad.
 *
 * The lane holds the plane's icon, and the fold chevron in its place (the two
 * share one grid cell, see `railLane`). It is a fixed width whether or not it
 * holds a control, which is what keeps titles at every depth on one left
 * edge. Laid out in flow, never positioned, so the twisty can not land on the
 * first letter of the title again.
 */

/** Left pad for a row at `depth`, as an inline style (depth is data). */
export function railIndent(depth: number): { paddingLeft: string } {
	return { paddingLeft: `calc(var(--rail-row-pad) + ${depth} * var(--rail-indent))` };
}

/* ============================== The aside =============================== */

/** Rail width bounds, px. */
export const RAIL_WIDTH = { MIN: 200, DEFAULT: 260, MAX: 540 } as const;

/**
 * The rail itself. Its own surface, a hairline edge on `nuspace-edge` so it
 * holds in light too. The width is inline (the user drags it, see
 * sidebar/useRailWidth.ts), so none is set here.
 *
 * Collapsed, it is `hidden` rather than unmounted: the Add plane popup lives
 * in the rail and a pane's `...` still has to open it.
 */
export function railAside(collapsed: boolean): string {
	return cn(
		"relative flex shrink-0 flex-col",
		"border-r border-nuspace-edge bg-nuspace-rail",
		collapsed && "hidden",
	);
}

/** The drag strip on the rail's right edge. See ./resize.ts. */
export const railResizeHandle = resizeHandle("right");

/**
 * Top bar. `h-chrome`, like the pane bar and the tab bar, so the tops line up.
 * No rule under it: the search entry and the pins sit right under it, and
 * the header group ends where the body starts (`railScroll`). `rail-bar-pad` puts a button's
 * glyph on the rows' icon edge.
 */
export const railHeader = "flex h-chrome shrink-0 items-center gap-0.5 px-rail-bar-pad";

/**
 * The wordmark beside the collapse button: NUSPACE, the "nu" in accent and
 * the rest in the primary text color, so it reads white in dark theme.
 */
export const railWordmark =
	"ml-1.5 select-none font-semibold text-sm text-text-primary uppercase tracking-wider";
export const railWordmarkNu = "text-accent";

/**
 * Bottom bar: links on the left, the window's own state on the right. An edge
 * to edge rule over it, mirroring the divider under the header group.
 */
export const railFooter =
	"flex h-chrome shrink-0 items-center gap-0.5 border-t border-nuspace-edge px-rail-bar-pad";

/** The free middle of the bottom bar, between the links and the window's state. */
export const railFooterSpace = "min-w-0 flex-1";

/**
 * A top or bottom bar button, on top of a kit `IconButton ghost sm` with the
 * inset ring. The kit's look, one size up: 28px with a 16px glyph.
 */
export const railChromeButton = "size-7 [&_svg]:size-4";

/** The shortcut's kit `Shortcut` after a chrome button's tooltip text. */
export const railTooltipHint = "ml-1.5";

/**
 * The connection state: the kit's `StatusDot` in a button-sized box, so its
 * tooltip has something to hang on and a keyboard can reach it.
 */
export const railStatus = cn(
	"flex size-7 shrink-0 items-center justify-center rounded-md",
	"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring",
);

/**
 * The body under the header group, the rail's one scroller: the tree, its
 * sticky New plane row first, which is what marks the edge rows pass under.
 * `rail-inset` keeps a row's fill off both rail edges. `rail-top-gap` above
 * and again inside, as pad rather than margin, so a focus ring at the top
 * is not clipped.
 */
export const railScroll = cn(
	"mt-rail-top-gap flex min-h-0 flex-1 flex-col overflow-y-auto overflow-x-hidden",
	"px-rail-inset pt-rail-top-gap pb-1",
);

/**
 * New plane, at the top level: the tree's first row, shaped and spaced like
 * the rows under it, so it reads as the place the next plane goes. Sticky at
 * the top of the body, on the rail's own fill, so it stays at hand however
 * far the tree scrolls. The body pads its top (`railScroll`), and the strip
 * above the row covers that pad, so no row shows over it while they pass
 * under. Its own text one tier back, the `+` in the icon lane, the shortcut
 * on the actions' edge while it is hovered.
 */
export const railNewPlaneBar = cn(
	"sticky top-0 z-10 shrink-0 bg-nuspace-rail pb-rail-row-gap",
	"before:absolute before:inset-x-0 before:bottom-full before:h-rail-top-gap before:bg-nuspace-rail",
);

export const railNewPlane = cn(railRow(false, true), "w-full cursor-pointer text-left");

export const railNewPlaneIcon = "size-4 shrink-0 text-text-muted group-hover/row:text-text-primary";

export const railNewPlaneLabel = cn(
	"min-w-0 flex-1 truncate text-lg text-text-muted",
	"transition-colors duration-fast ease-out group-hover/row:text-text-primary",
);

export const railNewPlaneKeys = cn(
	"shrink-0 opacity-0 transition-opacity duration-fast ease-out",
	"group-hover/row:opacity-100 group-focus-visible/row:opacity-100",
);

/** The tree itself: rows a hairline apart, so two fills never merge. */
export const railTreeList = "flex flex-col gap-rail-row-gap";

/* ============================== The row ================================= */

/**
 * The row shell. This is what paints hover and selection, not the link inside
 * it, so the wash spans the whole line including the icon and the action lane.
 * A wash that stops short of the controls sitting on it reads as two elements.
 *
 * Every tier is a neutral gray (`rail-*` in tokens.css): hover, a plane open
 * in some other pane, and the focused pane's plane, strongest. The text never
 * changes hue, only steps up to the primary tier.
 *
 * `inset` pads the row's own left edge. A tree row leaves it off because
 * `railIndent(depth)` already supplies the offset; a flat row turns it on.
 */
export function railRow(selected: boolean, inset = false, open = false): string {
	return cn(
		"group/row relative flex items-center rounded-md",
		"h-rail-row pr-rail-row-pad-end",
		inset && "pl-rail-row-pad",
		"transition-colors duration-fast ease-out",
		// The row is the tree item, so the row carries the focus ring. Offset 0:
		// the kit's 2px offset gets clipped by the rail's own overflow.
		"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-0",
		selected
			? "bg-nuspace-rail-selected"
			: open
				? "bg-nuspace-rail-open hover:bg-nuspace-rail-hover"
				: "hover:bg-nuspace-rail-hover active:bg-doc-active",
	);
}

/**
 * The icon lane: one grid cell the plane's icon and the fold chevron stack
 * into, so they swap in place with no layout shift and no positioning. It is
 * also the `lane` group, which is how the icon hears that the chevron beside
 * it has keyboard focus.
 */
export const railLane = cn(
	"group/lane grid w-rail-lane shrink-0 place-items-center *:[grid-area:1/1]",
	"mr-rail-gap",
);

/*
 * The swap, in CSS only. At rest every row shows its icon, parent or leaf,
 * folded or open. While the row is hovered, or it or its chevron has keyboard
 * focus, the chevron shows instead. JS hover state is not used on purpose: it
 * flickers, and it sticks after a drag because the browser never sends the
 * leave. `group-hover/row` is scoped to the nearest row by name, and the rows
 * are flat siblings in the tree (see sidebar/RailTree.tsx), so hovering one
 * row never swaps another.
 *
 * `swap` is off while a drag is in flight, so no row sits in its hover look
 * while a plane travels over it.
 */
const ICON_OUT =
	"group-hover/row:opacity-0 group-focus-visible/row:opacity-0 group-has-focus-visible/lane:opacity-0";
const CHEVRON_IN =
	"group-hover/row:opacity-100 group-focus-visible/row:opacity-100 focus-visible:opacity-100";

/**
 * The plane's icon. Not a control: it takes no pointer events, so even at
 * opacity 0 (which lifts it into its own stacking layer, on top of the
 * chevron) it never catches the chevron's click.
 */
export function railIcon(swap: boolean): string {
	return cn(
		"pointer-events-none size-4 shrink-0 text-text-muted",
		"transition-opacity duration-fast ease-out",
		swap && ICON_OUT,
	);
}

/**
 * The fold chevron, on top of a kit `IconButton ghost xs` (a 20px box that
 * only fills when the pointer is on the chevron itself), in the icon's place.
 * Hidden at rest, shown by the swap above.
 */
export function railTwisty(swap: boolean): string {
	return cn(
		"opacity-0 transition-[opacity,background-color,color] duration-fast ease-out",
		swap && CHEVRON_IN,
	);
}

/** The chevron glyph: points right when folded, down when open. */
export function railChevron(open: boolean): string {
	return cn("transition-transform duration-fast ease-out", open && "rotate-90");
}

/**
 * What an open plane with no planes inside shows under itself: the kit's
 * `EmptyState`, one row tall and at the child's indent rather than centred.
 * Pair with `railIndent(depth + 1)`.
 */
export const railNoPlanes = "h-rail-row items-start py-0";

/**
 * The label, on top of a kit `NavLink`. NavLink stays because it is a real
 * anchor (cmd-click, middle-click, `aria-current="page"` for free). What it
 * does not own here is the look: the row shell paints the background, so both
 * of NavLink's washes are zeroed, and the open row's text steps up to the
 * primary tier instead of turning accent. 14px, regular weight.
 *
 * `ring-offset-0` because the kit's 2px focus offset gets clipped by the
 * rail's own overflow.
 */
export const railLabel = cn(
	"h-full min-w-0 flex-1 gap-0 px-0",
	"text-lg font-normal text-text-secondary",
	"bg-transparent hover:bg-transparent hover:text-text-primary group-hover/row:text-text-primary",
	"aria-[current=page]:bg-transparent aria-[current=page]:font-normal aria-[current=page]:text-text-primary",
	"data-[active=true]:bg-transparent data-[active=true]:font-normal data-[active=true]:text-text-primary",
	"focus-visible:ring-offset-0",
);

export const railTitle = "min-w-0 flex-1 truncate";

/** Placeholder for a row with no name yet. One tier back, never italic. */
export const railTitleEmpty = cn(railTitle, "text-text-muted");

/**
 * The action lane. It takes no width at rest and the lane's full width
 * (--rail-actions, room for its three buttons) only while revealed, so a
 * title at rest runs to the row's real edge instead of truncating against
 * buttons nobody can see. On reveal the title cuts off earlier; the row's
 * height never moves. The buttons sit at its right end, so the `...` stays on
 * the rail's right edge.
 *
 * Collapsing rather than overlaying the end of the row: an overlay would need
 * a fade matched to every row wash (rest, hover, open, selected, pressed) to
 * keep text from showing under the glyphs, and the reflow it saves is only
 * the truncation point moving.
 *
 * Hidden is `w-0`, never `display: none`, so the buttons stay in the DOM and
 * reachable by keyboard; keyboard focus inside reveals them. Hidden controls
 * are also click-through, because an invisible button that still eats a click
 * is worse than no button.
 *
 * Revealed by hover, by keyboard focus on the row or inside the lane, and
 * while a menu it opened is open. A mouse click does not: clicking a row
 * focuses it, and the open row should not keep its buttons up after.
 */
export const railActions = cn(
	"flex w-0 shrink-0 items-center justify-end gap-px overflow-hidden",
	"pointer-events-none opacity-0",
	"transition-opacity duration-fast ease-out",
	"group-hover/row:pointer-events-auto group-hover/row:w-rail-actions group-hover/row:opacity-100",
	"group-focus-visible/row:pointer-events-auto group-focus-visible/row:w-rail-actions group-focus-visible/row:opacity-100",
	"has-focus-visible:pointer-events-auto has-focus-visible:w-rail-actions has-focus-visible:opacity-100",
	// Keep them up while a menu they opened is still open
	"[&:has([data-state=open])]:pointer-events-auto [&:has([data-state=open])]:w-rail-actions [&:has([data-state=open])]:opacity-100",
);

/**
 * Split, `+` and `...`, on top of a kit `IconButton ghost sm` with the inset
 * ring: a 16px glyph in its 24px box, the `...` glyph on the rail's right
 * edge (tokens.css).
 */
export const railAction = "rounded-sm [&_svg]:size-4";

/** Wrapper around a row, which the drop line positions against. */
export const railRowWrap = "relative";

/* ============================== Inline edit ============================= */

/**
 * Rename happens in place, in the row, on top of a kit `Input` shrunk to the
 * row. The rail used to reach for `window.prompt`, which freezes the whole
 * tab, cannot be styled, cannot be themed, and drops you out of the document
 * you were reading. It is not a dialog, it is an absence of one.
 */
export const railInputBox = "flex min-w-0 flex-1 items-center";

export const railInput = "h-6 min-w-0 flex-1 px-1 py-0 text-lg";

/* ============================== Empty + loading ========================= */

/** Row-shaped placeholder, so the rail does not resize when the list lands. */
export function railSkeletonRow(inset = false): string {
	return cn("flex h-rail-row items-center pr-rail-row-pad-end", inset && "pl-rail-row-pad");
}

/** The bar inside a skeleton row, on top of a kit `Skeleton`. */
export const railSkeletonBar = "h-3 w-full rounded-sm";

/* ============================== Drag and drop =========================== */

/**
 * Where a dragged row would land. A thin accent line between rows for a
 * sibling drop, drawn at the target row's indent so it says which level the
 * row lands on; the whole target row ringed for a drop into it. The accent is
 * fine here: a drag is a moment, not a resting state.
 */
export function railDropLine(edge: "before" | "after"): string {
	return cn(
		"pointer-events-none absolute right-0 h-0.5 rounded-full bg-accent",
		edge === "before" ? "-top-px" : "-bottom-px",
	);
}

/** The line's left edge, at the title of a row at `depth`. */
export function railDropLineStyle(depth: number): { left: string } {
	return {
		left: `calc(var(--rail-row-pad) + ${depth} * var(--rail-indent) + var(--rail-lane))`,
	};
}

/** A row being dropped into: ringed, so it reads apart from the selection wash. */
export const railDropInto = "rounded-md ring-2 ring-accent ring-inset";

/** The row being dragged, dimmed while it travels. */
export const railDragging = "opacity-50";

/** The space under the last row. A drop here moves the row to the top level, last. */
export const railDropTail = "relative min-h-8 flex-1";

/* ============================== Pinned ================================== */

/*
 * The pinned row, the last strip of the header group under the search entry:
 * one tiled icon per pinned plane, in a strip that scrolls sideways with no
 * scrollbar, fixed while the tree scrolls under it. The first box starts on
 * the search entry's edge, and its size (`rail-pin`, tokens.css) is the
 * entry's lead around the glyph on every side, so header button, search
 * glyph, pins and row icons share one centre line with nothing to offset.
 */

/**
 * The shelf around the strip, on the rows' edges. `rail-top-gap` above it,
 * the header group's one step, the same as between two pins; below it the
 * divider's own step, so with no pins nothing is left over.
 */
export const railPinShelf = "mt-rail-top-gap shrink-0 px-rail-inset";

/** The strip. Its mask is `railPinsFade`, inline, since which edges fade is data. */
export const railPins = cn(
	"flex shrink-0 items-center gap-rail-top-gap overflow-x-auto overflow-y-hidden",
	"scrollbar-none",
);

/**
 * A soft fade on each edge with more behind it, as a mask so it works on any
 * surface in either theme. `--rail-fade` wide.
 */
export function railPinsFade(start: boolean, end: boolean): { maskImage?: string } {
	if (!start && !end) return {};
	const from = start ? "transparent, black var(--rail-fade)" : "black";
	const to = end ? "black calc(100% - var(--rail-fade)), transparent" : "black";
	return { maskImage: `linear-gradient(to right, ${from}, ${to})` };
}

/**
 * One pinned plane: its icon on a kit `IconButton soft sm` with the inset
 * ring, a filled tile with no border like the rail's rows, sized to
 * `rail-pin` (36px square, tokens.css) with a 16px glyph. Washed like a tree row: the focused pane's plane strongest, one
 * open elsewhere lighter, the rest on the kit's resting wash.
 */
export function railPin(selected: boolean, open: boolean): string {
	return cn(
		"relative size-rail-pin shrink-0 [&_svg]:size-4",
		"focus-visible:ring-offset-0",
		selected
			? "bg-nuspace-rail-selected text-text-primary hover:bg-nuspace-rail-selected"
			: open
				? "bg-nuspace-rail-open hover:bg-nuspace-rail-hover hover:text-text-primary"
				: "hover:bg-nuspace-rail-hover hover:text-text-primary active:bg-doc-active",
	);
}

/** Where a drop lands among the pins: a thin accent line on one side of an icon. */
export function railPinDropLine(edge: "before" | "after"): string {
	return cn(
		"pointer-events-none absolute inset-y-1 w-0.5 rounded-full bg-accent",
		edge === "before" ? "-left-0.5" : "-right-0.5",
	);
}

/* ================================ Search ================================= */

/*
 * The search entry, under the top bar: the two and the pins read as one
 * header group, which the body (`railScroll`) closes.
 *
 * It is a row, not an input. Same inset, height, radius and lanes as a flat
 * plane row, so its glyph sits on the rail's one left edge and its label on
 * the titles' edge. At rest it carries its own quiet fill (`nuspace-rail-search`), so it
 * reads as a place to type without a box around it; hover steps it up to the selected
 * tier and the label up to the secondary text tier. No border in any state.
 */

/** The strip holding the entry, on the rows' edges. */
export const railSearch = "shrink-0 px-rail-inset";

export const railSearchTrigger = cn(
	"group/search flex h-rail-row w-full cursor-pointer items-center rounded-md",
	"pl-rail-row-pad pr-rail-row-pad-end",
	"bg-nuspace-rail-search text-base text-text-muted",
	"transition-colors duration-fast ease-out",
	"hover:bg-nuspace-rail-selected hover:text-text-secondary active:bg-nuspace-rail-selected",
	"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-0",
);

/**
 * A plane's menu, off its `...` or a right-click: wide enough that a label and
 * its shortcut caps never crowd each other.
 */
export const railMenu = "min-w-52";

/** The search glyph, in a row's icon lane and at a row icon's size. */
export const railSearchIcon = cn(railLane, "[&_svg]:size-4");

export const railSearchText = "min-w-0 flex-1 truncate text-left";

/** The shortcut at the far end: a kit `Shortcut` chip, apart from the label. */
export const railSearchHint = "shrink-0";

/** One kind to search in the popup: its box, then its label. */
export const searchItem = "gap-3";

/** Under the popup's rows: the Enter hint, then the button. */
export const searchFooter =
	"flex items-center justify-between gap-2 border-t border-border-subtle px-3 py-2";

export const searchHint = "flex items-center gap-1.5 text-xs text-text-muted";
