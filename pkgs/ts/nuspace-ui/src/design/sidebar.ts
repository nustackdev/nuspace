// Sidebar class recipes + geometry. The sidebar's whole vocabulary.
//
// The sidebar floats on the canvas (`ground-deep`, the shell's root) with no
// surfaces of its own: no fill, no border, its groups apart by spacing only
// (10px). A fixed header and footer, everything between in the kit's
// `ScrollArea`.
//
// Five pieces, one variant each (../sidebar/): the header, the footer, the
// section, the row and the action row. Every row is the same 28px line: an
// icon lane, a truncating label in `ink-2`, and one optional trailing thing
// (a shortcut, a count or a hover action). One selected state for all: a
// quiet gray fill (`sidebar-a`, theme.css), which is also where a row under
// the pointer lands. The text never changes hue, it steps up to the primary
// tier. A tree row is the same row, indented.
//
// The lengths are stated once, here, on the 4px grid:
//
// ```
//  |<- 8 + depth*20 ->|<- 20 ->|<- 8 ->| label ... |<- trailing ->|<- 6 ->|
//  |                  |  icon  |       | truncates | shortcut,    |       |
//  |                  |        |       |           | count, action|       |
// ```
//
// Everything resolves to kit L2/L4 semantic names or the nuspace frame roles
// in ./theme.css. No raw hex.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §4 row heights, §1 grid
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers, §2.4 wash
//   go/projects/nustackdev/design/motion.md         §3 nav rows
//   go/projects/nustackdev/design/a11y.md           §4 aria, §5 focus ring

import { cn } from "@nustackdev/ui-kit";

/* ============================== Geometry ================================= */

/** Left pad for a row at `depth`, as an inline style (depth is data). */
export function sidebarIndent(depth: number): { paddingLeft: string } {
	return { paddingLeft: `calc(0.5rem + ${depth} * 1.25rem)` };
}

/**
 * A control inside a row or a section title (chevron, `+`, `...`, a section
 * action): over the kit's ghost wash, it paints only the control step
 * (`sidebar-cd`, theme.css), one on hover, two on press and while its menu is
 * open. The step lands on the row's own fill, so a control always climbs from
 * whatever the row shows.
 */
const sidebarControlWash =
	"hover:bg-sidebar-cd1 active:bg-sidebar-cd2 data-[state=open]:bg-sidebar-cd2";

/* ============================== The sidebar ============================== */

/**
 * The sidebar itself, filling the split panel it sits in. The panel owns the
 * width and the fold (../shell/Shell.tsx). No fill: the canvas shows.
 */
export const sidebarAside = "relative flex min-w-0 flex-1 flex-col";

/** The scroller between the header and the footer: the kit's `ScrollArea`. */
export const sidebarScroll = "min-h-0 flex-1";

/**
 * Its viewport. Radix pins `overflow-y: scroll` inline, a lane the browser may
 * draw even with nothing to scroll; the kit's overlay bar is the only one we
 * want, so the viewport scrolls only when it must.
 */
export const sidebarScrollViewport = "overflow-y-auto!";

/**
 * The body inside the scroller: the sections, 10px apart, inset 8px from
 * both edges. It holds the focus a click leaves, which shows nowhere.
 */
export const sidebarBody = "flex flex-col gap-2.5 px-2 py-1 outline-hidden";

/* ============================== Header, footer =========================== */

/**
 * The fixed top bar, lined up with the first pane's header: 6px down like the
 * desk area (its `py-1.5`), then as tall as a pane's top border and header
 * (1px + 34px), so its buttons sit on the header's center line.
 */
export const sidebarHeader = "mt-1.5 flex h-[35px] shrink-0 items-center gap-0.5 px-3";

/** A header button pushed to the bar's right end. */
export const sidebarHeaderEnd = "ml-auto";

/** NUSPACE next to the collapse button, the "nu" in accent text. */
export const sidebarWordmark =
	"ml-1.5 select-none font-semibold text-sm text-text-primary uppercase tracking-wider";
export const sidebarWordmarkNu = "text-accent-text";

/**
 * The fixed bottom bar: links on the left, the window's own state on the
 * right. No rule. 6px off the bottom edge, like the desk area.
 */
export const sidebarFooter = "mb-1.5 flex h-chrome shrink-0 items-center gap-0.5 px-3";

/** The free middle of the bottom bar. */
export const sidebarFooterSpace = "min-w-0 flex-1";

/** A header or footer button, on a kit `IconButton ghost sm`: 28px, a 16px glyph. */
export const sidebarChromeButton = "size-7 [&_svg]:size-4";

/** The shortcut's kit `Shortcut` after a tooltip's text. */
export const sidebarTooltipHint = "ml-1.5";

/** The connection dot, in a button-sized box a keyboard can reach. */
export const sidebarStatus = cn(
	"flex size-7 shrink-0 items-center justify-center rounded-md",
	"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring",
);

/* ============================== Rail ===================================== */

/*
 * What the sidebar folds to (../sidebar/SidebarRail.tsx): a 48px column of
 * 28px icon buttons, centered, on the canvas like the sidebar. Its toggle sits
 * in a bar as tall as the header, so it stays where the header had it.
 */

/** The rail's width: the size the shell's sidebar panel folds to. */
export const SIDEBAR_RAIL_PX = 48;

/** The rail itself: the whole of the folded sidebar panel, `SIDEBAR_RAIL_PX` wide. */
export const sidebarRail = "flex w-12 shrink-0 flex-col";

/** The rail's top bar: just the toggle, on the header's line (`sidebarHeader`). */
export const sidebarRailHead = "mt-1.5 flex h-[35px] shrink-0 items-center justify-center";

/** The rail's scroller: 6px off the bottom edge, like the desk area. */
export const sidebarRailScroll = "mb-1.5 min-h-0 flex-1";

/** The icons, one column, a hairline apart like the sidebar's rows. */
export const sidebarRailBody = "flex flex-col items-center gap-px py-1";

/** Between the groups (nav, desks, planes): a short hairline, 8px of room each side. */
export const sidebarRailDivider = "my-2 h-px w-5 shrink-0 border-0 bg-border-subtle";

/** One icon: a row's look squeezed to its icon, the same selected fill. */
export function sidebarRailItem(selected: boolean): string {
	return cn(
		"text-text-muted hover:text-text-primary",
		selected
			? "bg-sidebar-a-fill text-text-primary hover:bg-sidebar-a-hover active:bg-sidebar-a-press"
			: "hover:bg-sidebar-a-fill active:bg-sidebar-a-hover",
	);
}

/** A desk's first letter, where a plane has its icon. */
export const sidebarRailMonogram = "select-none text-sm font-medium leading-none";

/* ============================== Section ================================== */

/** One section: an optional title line over its body, a hairline apart like its rows. */
export const sidebarSection = "flex shrink-0 flex-col gap-px";

/**
 * The title line, built like a row: the same 28px item, radius, padding and
 * hover fill, so a title reads as one more item and its actions sit in it as
 * a row's do. Only its text says heading.
 */
export const sidebarSectionHead = cn(
	"group/section relative flex h-7 shrink-0 items-center gap-1 rounded-md pr-1.5",
	"transition-colors duration-fast ease-out",
	"hover:bg-sidebar-a-fill has-[>button[aria-expanded]:active]:bg-sidebar-a-hover",
);

/**
 * The title itself, filling the item: the label a size down and one tier
 * back, at the row's left padding. A button when it folds the section, so
 * the whole item folds it.
 */
export const sidebarSectionTitle = cn(
	"flex h-full min-w-0 flex-1 items-center gap-1 rounded-md pl-2 text-left",
	"select-none text-sm font-medium text-text-muted",
	"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
);

/** A title that is a button: the text a step up while the item is hovered. */
export const sidebarSectionTitleButton = "group-hover/section:text-text-secondary";

export const sidebarSectionLabel = "truncate";

/** The fold chevron after the title, shown while the title line is hovered. */
export function sidebarSectionChevron(open: boolean): string {
	return cn(
		"size-3 shrink-0 transition-[opacity,transform] duration-fast ease-out",
		"opacity-0 group-hover/section:opacity-100",
		open && "rotate-90",
	);
}

/** The count after the title. */
export const sidebarSectionCount = "shrink-0 select-none text-sm text-text-muted tabular-nums";

/**
 * The right actions, on the rows' right edge, each shown while the title line
 * is hovered, one of them has keyboard focus or a menu open.
 */
export const sidebarSectionActions = cn(
	"flex shrink-0 items-center gap-px",
	"*:opacity-0 *:transition-opacity *:duration-fast *:ease-out",
	"group-hover/section:*:opacity-100 has-focus-visible:*:opacity-100",
	"[&:has([data-state=open])]:*:opacity-100",
);

/**
 * A section action, on a kit `IconButton ghost sm`: a row action's look and
 * size, since the title line is an item like a row.
 */
export const sidebarSectionAction = cn(sidebarControlWash, "rounded-sm [&_svg]:size-4");

/** Rows a hairline apart, so two fills never merge. */
export const sidebarRows = "flex flex-col gap-px";

/* ============================== Row ====================================== */

/**
 * The row. This is what paints hover and selection, not the link inside it,
 * so the wash spans the whole line. A row rests on nothing and hovers to the
 * selected fill; the selected row climbs a step on hover and two on press.
 */
export function sidebarRow(selected: boolean, inset = false): string {
	return cn(
		"group/row relative flex h-7 items-center rounded-md pr-1.5",
		inset && "pl-2",
		"text-lg text-text-secondary hover:text-text-primary",
		"transition-colors duration-fast ease-out",
		// Offset 0: the kit's 2px offset gets clipped by the scroller.
		"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-0",
		selected
			? "bg-sidebar-a-fill text-text-primary hover:bg-sidebar-a-hover active:bg-sidebar-a-press"
			: "hover:bg-sidebar-a-fill active:bg-sidebar-a-hover",
	);
}

/**
 * The icon lane: one grid cell, so a tree row's icon and its fold chevron
 * stack and swap in place. It is also the `lane` group, so the icon hears
 * when the chevron next to it has keyboard focus.
 */
export const sidebarLane = cn(
	"group/lane mr-2 grid w-5 shrink-0 place-items-center *:[grid-area:1/1]",
	"text-text-muted [&_svg]:size-4",
);

/*
 * The swap, in CSS only: at rest a tree row shows its icon; hovered, or with
 * it or its chevron keyboard focused, the chevron instead. Off while a drag
 * is in flight, so no row sits in its hover look under a dragged plane.
 */
const ICON_OUT =
	"group-hover/row:opacity-0 group-focus-visible/row:opacity-0 group-has-focus-visible/lane:opacity-0";
const CHEVRON_IN =
	"group-hover/row:opacity-100 group-focus-visible/row:opacity-100 focus-visible:opacity-100";

/**
 * A row's icon. Not a control: it takes no pointer, so at opacity 0 (on top
 * of the chevron) it never catches the chevron's click.
 */
export function sidebarIcon(swap: boolean): string {
	return cn(
		"pointer-events-none size-4 shrink-0 text-text-muted",
		"transition-opacity duration-fast ease-out",
		swap && ICON_OUT,
	);
}

/** The fold chevron as a control, on a kit `IconButton ghost xs`, hidden at rest. */
export function sidebarTwisty(swap: boolean): string {
	return cn(
		sidebarControlWash,
		"opacity-0 transition-[opacity,background-color,color] duration-fast ease-out",
		swap && CHEVRON_IN,
	);
}

/** The fold chevron as a glyph, for a row that is one button (a spec group). */
export function sidebarLaneChevron(open: boolean): string {
	return cn(
		"size-4 text-text-muted opacity-0 transition-[opacity,transform] duration-fast ease-out",
		CHEVRON_IN,
		open && "rotate-90",
	);
}

/** The chevron glyph: right when folded, down when open. */
export function sidebarChevron(open: boolean): string {
	return cn("transition-transform duration-fast ease-out", open && "rotate-90");
}

/**
 * The label on a link row, on top of a kit `NavLink`: a real anchor, but the
 * row paints the look, so all of NavLink's washes are zeroed.
 */
export const sidebarLink = cn(
	"h-full min-w-0 flex-1 gap-0 px-0",
	"text-lg font-normal text-text-secondary",
	"bg-transparent hover:bg-transparent active:bg-transparent hover:text-text-primary group-hover/row:text-text-primary",
	"aria-[current=page]:bg-transparent aria-[current=page]:font-normal aria-[current=page]:text-text-primary",
	"data-[active=true]:bg-transparent data-[active=true]:font-normal data-[active=true]:text-text-primary",
	"focus-visible:ring-offset-0",
);

/** The label on a row that is not a link. */
export const sidebarLabel = "flex h-full min-w-0 flex-1 cursor-default select-none items-center";

export const sidebarTitle = "min-w-0 flex-1 truncate";

/** Placeholder for a row with no name yet: one tier back. */
export const sidebarTitleEmpty = cn(sidebarTitle, "text-text-muted");

/** A trailing shortcut or count: always shown, at the row's end. */
export const sidebarTrailing = "ml-2 shrink-0";

export const sidebarCount = cn(sidebarTrailing, "select-none text-sm text-text-muted tabular-nums");

/**
 * The trailing hover actions (one or a few buttons). No width at rest, so a
 * title runs to the row's end; their own width while shown, by hover, by
 * keyboard focus on the row or in it, and while a menu one opened is open.
 * Hidden is `w-0`, not `display: none`, so the keyboard still reaches them,
 * and click-through while hidden.
 */
export const sidebarHoverAction = cn(
	"flex w-0 shrink-0 items-center justify-end gap-px overflow-hidden",
	"pointer-events-none opacity-0 transition-opacity duration-fast ease-out",
	"group-hover/row:pointer-events-auto group-hover/row:w-auto group-hover/row:opacity-100",
	"group-focus-visible/row:pointer-events-auto group-focus-visible/row:w-auto group-focus-visible/row:opacity-100",
	"has-focus-visible:pointer-events-auto has-focus-visible:w-auto has-focus-visible:opacity-100",
	"[&:has([data-state=open])]:pointer-events-auto [&:has([data-state=open])]:w-auto [&:has([data-state=open])]:opacity-100",
);

/** The hover action's button, on a kit `IconButton ghost sm` with the inset ring. */
export const sidebarRowAction = cn(sidebarControlWash, "rounded-sm [&_svg]:size-4");

/**
 * The original plane's icon on a navigated desk row, as a control on a kit
 * `IconButton ghost xs` in the icon lane: a click resets the row.
 */
export const sidebarResetIcon = cn(sidebarControlWash, "rounded-sm");

/** The slash between a navigated row's original icon and its recent title. */
export const sidebarCrumbSlash = "mr-1.5 shrink-0 select-none text-text-muted";

/** A tooltip holding a sentence (a spec's description): wraps rather than runs on. */
export const sidebarTooltipWide = "max-w-64 text-pretty";

/* ============================== Rename =================================== */

/** Rename in place, on a kit `Input` shrunk to the row. */
export const sidebarInput = "h-6 min-w-0 flex-1 px-1 py-0 text-lg";

/* ============================== Tree ===================================== */

/**
 * What an open plane with no planes inside shows under itself: the kit's
 * `EmptyState`, one row tall, at the child's indent. Pair with
 * `sidebarIndent(depth + 1)`.
 */
export const sidebarNoPlanes = "h-7 items-start py-0";

/** Wrapper around a tree row, which the drop line positions against. */
export const sidebarRowWrap = "relative";

/**
 * Where a dragged row would land: the accent line between rows for a sibling
 * drop, at the target row's indent; the whole row ringed for a drop into it.
 */
export function sidebarDropLine(edge: "before" | "after"): string {
	return cn(
		"pointer-events-none absolute right-0 h-0.5 rounded-full bg-accent",
		edge === "before" ? "-top-px" : "-bottom-px",
	);
}

/** The line's left edge, at the label of a row at `depth`. */
export function sidebarDropLineStyle(depth: number): { left: string } {
	return { left: `calc(0.5rem + ${depth} * 1.25rem + 1.75rem)` };
}

export const sidebarDropInto = "ring-2 ring-accent ring-inset";

/**
 * An empty desk's body: a row's box (full width, 28px, its radius), its
 * outline dashed and drawn inside so it takes no room, a small muted line of
 * text, and a drop target for the first item. Ringed like a row while a drag
 * aims at it.
 */
export const sidebarDeskEmpty = cn(
	"flex h-7 select-none items-center rounded-md px-2",
	"outline-1 -outline-offset-1 outline-border-default outline-dashed",
	"text-sm text-text-muted",
);

/** The row being dragged, dimmed while it travels. */
export const sidebarDragging = "opacity-50";

/**
 * The space under the last tree row: a drop here moves the row to the top
 * level, last. It lies over the gap to the next section and takes no room of
 * its own, so every section ends at its last row and the gaps stay even.
 */
export const sidebarDropTail = "relative -mt-px -mb-2.5 h-2.5 shrink-0";

/* ============================== Loading ================================== */

/** Row-shaped placeholder, so the sidebar does not move when the tree lands. */
export const sidebarSkeletonRow = "flex h-7 items-center pr-1.5";

/** The bar inside a skeleton row, on a kit `Skeleton`. */
export const sidebarSkeletonBar = "h-3 w-full rounded-sm";
