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

/**
 * A control inside a row (chevron, split, +, ...): over the kit's ghost wash,
 * it paints only the rail's control step (`cd`, theme.css), one on hover,
 * two on press and while its menu is open. The step lands on the row's own fill, so the
 * control always climbs from whatever the row shows: at rest, hovered, open
 * elsewhere or selected.
 */
const railControlWash = "hover:bg-rail-cd1 active:bg-rail-cd2 data-[state=open]:bg-rail-cd2";

/** Left pad for a row at `depth`, as an inline style (depth is data). */
export function railIndent(depth: number): { paddingLeft: string } {
	return { paddingLeft: `calc(var(--rail-row-pad) + ${depth} * var(--rail-indent))` };
}

/* ============================== The aside =============================== */

/**
 * The rail itself, its own surface filling the split panel it sits in. The
 * panel owns the width, the fold and the hairline edge (the split's handle,
 * on `nuspace-edge`, see shell/Shell.tsx), so none of them is set here.
 *
 * Folded, the panel is inert rather than the rail unmounted: the Add plane
 * popup lives in the rail and a pane's `...` still has to open it.
 */
export const railAside = "relative flex min-w-0 flex-1 flex-col bg-nuspace-rail";

/**
 * Top bar. `h-chrome`, like the pane bar and the tab bar, so the tops line up.
 * No rule under it: the nav rows sit right under it, and the header group
 * ends where the body starts (`railScroll`). `rail-bar-pad` puts a button's
 * glyph on the rows' icon edge.
 */
export const railHeader = "flex h-chrome shrink-0 items-center gap-0.5 px-rail-bar-pad";

/** A top bar button pushed to the bar's right end, its glyph on the rows' right edge. */
export const railHeaderEnd = "ml-auto";

/**
 * The wordmark beside the collapse button: NUSPACE, the "nu" in accent-text and
 * the rest in the primary text color, so it reads white in dark theme.
 */
export const railWordmark =
	"ml-1.5 select-none font-semibold text-sm text-text-primary uppercase tracking-wider";
export const railWordmarkNu = "text-accent-text";

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
 * The body under the top bar, the rail's one scroller: the nav rows, then
 * the pinned, the planes and the extensions, each under its section header. `rail-inset` keeps a row's
 * fill off both rail edges. `rail-top-gap` top and bottom alike, as pad
 * rather than margin, so a focus ring at either end is not clipped.
 */
export const railScroll = cn(
	// No ring of its own: it holds the focus a click leaves, which shows nowhere.
	"flex min-h-0 flex-1 flex-col overflow-y-auto overflow-x-hidden outline-hidden",
	"px-rail-inset py-rail-top-gap",
);

/**
 * New plane, at the top level: the tree's first row, under the Planes header,
 * shaped and spaced like the rows under it, so it reads as the place the next
 * plane goes. Its own text one tier back, the `+` in the icon lane, the
 * shortcut on the actions' edge while it is hovered.
 */
export const railNewPlaneBar = "shrink-0 pb-rail-row-gap";

export const railNewPlane = cn(railRow(false, true), "w-full cursor-default text-left");

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
 * Fills are the rail's anchors (theme.css): a row rests on nothing, hovers
 * to a2 and presses one step past it. The focused pane's plane rests on a2,
 * a plane open in some other pane on a1, the quieter one, and both climb a
 * step on hover and two on press. The text never changes hue, only steps up
 * to the primary tier.
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
			? "bg-rail-a2-fill hover:bg-rail-a2-hover active:bg-rail-a2-press"
			: open
				? "bg-rail-a1-fill hover:bg-rail-a1-hover active:bg-rail-a1-press"
				: "hover:bg-rail-a2-fill active:bg-rail-a2-hover",
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
		railControlWash,
		"opacity-0 transition-[opacity,background-color,color] duration-fast ease-out",
		swap && CHEVRON_IN,
	);
}

/**
 * The fold chevron as a glyph rather than a control, for a row that is one
 * button (an extension's group): swapped in for the icon like `railTwisty`,
 * turned like `railChevron`.
 */
export function railLaneChevron(open: boolean): string {
	return cn(
		"size-4 text-text-muted opacity-0 transition-[opacity,transform] duration-fast ease-out",
		CHEVRON_IN,
		open && "rotate-90",
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
 * does not own here is the look: the row shell paints the background, so all
 * of NavLink's washes (hover, press, current) are zeroed, and the open row's
 * text steps up to the primary tier instead of turning accent. 14px, regular weight.
 *
 * `ring-offset-0` because the kit's 2px focus offset gets clipped by the
 * rail's own overflow.
 */
export const railLabel = cn(
	"h-full min-w-0 flex-1 gap-0 px-0",
	"text-lg font-normal text-text-secondary",
	"bg-transparent hover:bg-transparent active:bg-transparent hover:text-text-primary group-hover/row:text-text-primary",
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
export const railAction = cn(railControlWash, "rounded-sm [&_svg]:size-4");

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

/**
 * The space under the last row, a section gap tall, which is also the air
 * between the planes and the extensions under them. A drop here moves the
 * row to the top level, last.
 */
export const railDropTail = "relative min-h-rail-section-gap shrink-0";

/* ================================ Nav ================================== */

/*
 * The nav rows, the body's first: home, search and settings, the planes
 * that always exist. Flat rows on the tree rows' geometry, so their glyphs
 * sit on the rail's one left edge and their labels on the titles' edge. Not
 * tree rows: they never move, nest or go. Their shortcuts always show.
 */

/** The strip holding them, the body's first, on its edges; it scrolls with the body. */
export const railNav = "flex shrink-0 flex-col gap-rail-row-gap";

/** One nav row: a real link, washed like a tree row when its plane is open. */
export function railNavRow(selected: boolean, open: boolean): string {
	return cn(
		railRow(selected, true, open),
		"cursor-default text-lg text-text-secondary hover:text-text-primary",
		selected && "text-text-primary",
	);
}

/** The nav row's glyph, in the icon lane at a row icon's size. */
export const railNavIcon = cn(railLane, "text-text-muted [&_svg]:size-4");

export const railNavLabel = "min-w-0 flex-1 truncate";

/** The shortcut at the far end, inline, always shown: these keys are worth learning. */
export const railNavKeys = "shrink-0";

/* ============================== Sections ================================ */

/*
 * A section of the body (Pinned, Planes, Extensions): a quiet header over its rows.
 * The label one tier back and a size down, so it reads as a heading and not
 * a row. An action (the Planes `+`) sits on the rows' right edge, shown while
 * the header is hovered or holds the keyboard.
 */

export const railSection = cn(
	"group/section mt-rail-section-gap flex h-7 shrink-0 items-center first:mt-0",
	// Right under the tree's drop tail, which is a section gap tall already.
	"[[data-rail-tree]+&]:mt-0",
	"pl-rail-row-pad pr-rail-row-pad-end",
);

export const railSectionLabel =
	"min-w-0 flex-1 select-none truncate text-sm font-medium text-text-muted";

/** The header's action, on a kit `IconButton ghost sm` with the inset ring. */
export const railSectionAction = cn(
	railControlWash,
	"rounded-sm opacity-0 transition-opacity duration-fast ease-out [&_svg]:size-4",
	"group-hover/section:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100",
);

/* ============================== Extensions ============================== */

/**
 * An extension row's label, a group's package name or an entry's: plain text
 * on the label's tier where a plane row has its link, since the whole row is
 * the button, folding or making a plane rather than opening one.
 */
export const railGroupLabel = cn(
	"flex h-full min-w-0 flex-1 cursor-default select-none items-center truncate text-lg text-text-secondary",
	"transition-colors duration-fast ease-out group-hover/row:text-text-primary",
);

/** A tooltip holding a sentence (an extension entry's description): wraps rather than runs on. */
export const railTooltipWide = "max-w-64 text-pretty";

/* ============================== Menus =================================== */

/**
 * A plane's menu, off its `...` or a right-click: wide enough that a label and
 * its shortcut caps never crowd each other.
 */
export const railMenu = "min-w-52";
