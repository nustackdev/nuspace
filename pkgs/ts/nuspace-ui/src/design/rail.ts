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

/** Rail width bounds, px. DEFAULT is the old fixed w-60. */
export const RAIL_WIDTH = { MIN: 180, DEFAULT: 300, MAX: 480 } as const;

/**
 * The rail itself. Its own surface, a hairline edge on `rail-edge` so it holds
 * in light too. The width is inline (the user drags it, see
 * sidebar/useRailWidth.ts), so none is set here.
 *
 * Collapsed, it is `hidden` rather than unmounted: the Add plane popup lives
 * in the rail and a pane's `...` still has to open it.
 */
export function railAside(collapsed: boolean): string {
	return cn(
		"relative flex shrink-0 flex-col",
		"border-r border-rail-edge bg-bg-surface",
		collapsed && "hidden",
	);
}

/** The drag strip on the rail's right edge. See ./resize.ts. */
export const railResizeHandle = resizeHandle("right");

/**
 * Top bar. `h-chrome`, like the pane bar and the tab bar, so the tops line up.
 * No rule under it: the tree starts `rail-top-gap` below and a line would
 * only box it. `rail-bar-pad` puts a button's glyph on the rows' icon edge.
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
 * The free middle of the top bar, between the collapse button and the create
 * one. Empty for now; search goes here.
 */
export const railHeaderSpace = "min-w-0 flex-1";

/**
 * Bottom bar: links on the left, the window's own state on the right. No rule
 * over it, same as the top bar.
 */
export const railFooter = "flex h-chrome shrink-0 items-center gap-0.5 px-rail-bar-pad";

/** The bottom bar's free middle, where a settings button can go later. */
export const railFooterSpace = "min-w-0 flex-1";

/**
 * A top or bottom bar button, on top of a kit `IconButton ghost`. 28px with a
 * 16px glyph, muted until hovered, and hovered on the rail's own gray rather
 * than `bg-elevated`, which is white on a white rail in light.
 */
export const railChromeButton = cn(
	"size-7 rounded-md text-text-muted",
	"hover:bg-rail-hover hover:text-text-primary active:bg-doc-active",
	"focus-visible:ring-offset-0",
	"[&_svg]:size-4",
);

/** The shortcut after a chrome button's tooltip, a tier back. */
export const railTooltipHint = "ml-1 text-text-muted";

/**
 * The connection state, as a dot in a button-sized box so its tooltip has
 * something to hang on and a keyboard can reach it.
 */
export const railStatus = cn(
	"flex size-7 shrink-0 items-center justify-center rounded-md",
	"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring",
);

/** Healthy is the quiet case, so its green steps back; trouble is full strength. */
const STATUS_DOT: Record<"ok" | "info" | "warn" | "danger", string> = {
	ok: "bg-status-ok/50",
	info: "bg-status-info",
	warn: "bg-status-warn",
	danger: "bg-status-danger",
};

/** The dot itself. 6px; it pulses while the socket is trying. */
export function railStatusDot(tone: "ok" | "info" | "warn" | "danger", busy: boolean): string {
	return cn("size-1.5 rounded-full", STATUS_DOT[tone], busy && "animate-pulse");
}

/**
 * Scroll body. `rail-inset` keeps a row's fill off both rail edges, and
 * `rail-top-gap` gives the first row air under the top bar.
 */
export const railScroll = cn(
	"flex min-h-0 flex-1 flex-col overflow-y-auto overflow-x-hidden [scrollbar-gutter:stable]",
	"px-rail-inset pt-rail-top-gap pb-1",
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
			? "bg-rail-selected"
			: open
				? "bg-rail-open hover:bg-rail-hover"
				: "hover:bg-rail-hover active:bg-doc-active",
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
 * The fold chevron, on top of a kit `IconButton ghost`, in the icon's place.
 * Hidden at rest, shown by the swap above. A 20px box that only fills when
 * the pointer is on the chevron itself. `ghost` hovers to `bg-elevated`,
 * which inside an already-washed row reads as a chip stuck to the label, so
 * it is re-tinted onto the neutral tier.
 */
export function railTwisty(swap: boolean): string {
	return cn(
		"size-5 rounded-sm text-text-muted opacity-0",
		"transition-[opacity,background-color,color] duration-fast ease-out",
		swap && CHEVRON_IN,
		"hover:bg-doc-active hover:text-text-primary",
		"focus-visible:ring-offset-0",
		"[&_svg]:size-3.5",
	);
}

/** The chevron glyph: points right when folded, down when open. */
export function railChevron(open: boolean): string {
	return cn("transition-transform duration-fast ease-out", open && "rotate-90");
}

/**
 * What an open plane with no planes inside shows under itself: one muted,
 * non-interactive line at the child's indent. Pair with `railIndent(depth + 1)`.
 */
export const railNoPlanes = "flex h-rail-row select-none items-center text-base text-text-muted";

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
 * The action lane. Always in flow and always the same width (--rail-actions,
 * room for its three buttons), so the title truncates against a stable edge
 * and nothing reflows on hover; only the opacity moves. The buttons sit at
 * its right end, so the `...` stays on the rail's right edge. Hidden controls are also click-through, because an invisible
 * button that still eats a click is worse than no button.
 *
 * Keyboard focus shows it too, but a mouse click does not: clicking a row
 * focuses it, and the open row should not keep its buttons up after.
 */
export const railActions = cn(
	"flex w-rail-actions shrink-0 items-center justify-end gap-px",
	"pointer-events-none opacity-0",
	"transition-opacity duration-fast ease-out",
	"group-hover/row:pointer-events-auto group-hover/row:opacity-100",
	"group-focus-visible/row:pointer-events-auto group-focus-visible/row:opacity-100",
	"has-focus-visible:pointer-events-auto has-focus-visible:opacity-100",
	// Keep them up while a menu they opened is still open
	"[&:has([data-state=open])]:pointer-events-auto [&:has([data-state=open])]:opacity-100",
);

/**
 * Same re-tint as the twisty, for split, `+` and `...`. 16px glyph in a 24px box; the
 * `...` glyph lands on the rail's right edge (tokens.css).
 */
export const railAction = cn(
	"size-6 rounded-sm text-text-muted",
	"hover:bg-doc-active hover:text-text-primary",
	"focus-visible:ring-offset-0",
	"[&_svg]:size-4",
);

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

export const railInput = cn("h-6 min-w-0 flex-1 px-1 py-0 text-lg", "focus-visible:ring-offset-0");

/* ============================== Empty + loading ========================= */

/** Row-shaped placeholder, so the rail does not resize when the list lands. */
export function railSkeletonRow(inset = false): string {
	return cn("flex h-rail-row items-center pr-rail-row-pad-end", inset && "pl-rail-row-pad");
}

/** The bar inside a skeleton row, on top of a kit `Skeleton`. */
export const railSkeletonBar = "h-3 w-full rounded-sm";

export const railEmpty = cn("select-none px-rail-row-pad py-2 text-base text-text-muted");

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

/* ============================== Add plane =============================== */

/** One registered Plane in the Add plane popup: icon, label, description. */
export const addPlaneItem = "items-start [&_svg]:mt-0.5";

export const addPlaneText = "flex min-w-0 flex-col";

export const addPlaneLabel = "truncate text-sm text-text-primary uppercase tracking-wider";

export const addPlaneDescription = "truncate text-xs text-text-muted";
