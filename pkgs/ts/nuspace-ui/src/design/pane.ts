// Pane class recipes: the header across a pane's top, its body, and the
// settings menu off its `...`, a kit dropdown.
//
// The header is shell chrome, not document: it stays put while the plane
// under it scrolls in the body. About 34px, the plane's icon and title on the
// left, the actions on the right. No line under it: the header and the
// plane share one surface, the frame's top air keeps them apart.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §4 row heights
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers

import { cn } from "@nustackdev/ui-kit";

/** The header. The drag handle of its pane (`data-pane-header`). */
export const paneHeader =
	"flex h-8.5 shrink-0 items-center gap-1.5 pr-1 pl-2.5";

/** The plane's icon in the header. */
export const paneHeaderIcon = "shrink-0 text-text-muted";

/**
 * What every drag shows under the pointer, a pane header's and a sidebar
 * row's alike: a small chip of the icon and title, like a sidebar row, in
 * place of the browser's snapshot of what was grabbed. Drawn off screen just
 * long enough to be taken.
 */
export const dragChip = cn(
	"pointer-events-none fixed top-0 -left-[1000px] flex h-7 max-w-64 items-center gap-2",
	"rounded-md bg-bg-elevated px-2 text-sm text-text-primary shadow-raised",
	"[&>*:first-child]:mr-0 [&>*:first-child]:shrink-0 [&_svg]:size-4",
);

/**
 * The header's trail: the planes above this one, then its own title, on the
 * kit's breadcrumb. One line, filling the header up to its actions.
 */
export const paneCrumbs = "min-w-0 flex-1";

export const paneCrumbList = "min-w-0 flex-nowrap gap-1";

/**
 * A parent's crumb, and the `...` for the ones collapsed. They give way
 * first when the pane is narrow, so the plane's own title is the last to
 * truncate.
 */
export const paneCrumbParent = "min-w-0 shrink-[8]";

/** A parent's link. Muted like an unfocused title, up a tier on hover. */
export const paneCrumbLink = "block truncate text-sm text-text-muted hover:text-text-primary";

export const paneCrumbSep = "shrink-0";

/** The plane's own crumb, the last one. */
export const paneCrumbHere = "min-w-0";

/**
 * The header's title, the plane's own crumb: `ink-1` and a step heavier on
 * the focused pane, dimmed on the others.
 */
export function paneHeaderTitle(focused: boolean): string {
	return cn(
		"block min-w-0 select-none truncate text-sm",
		focused ? "font-medium text-text-primary" : "font-normal text-text-muted",
	);
}

/**
 * The header's actions: shown on hover, on the focused pane, and while one of
 * them is open or has the keyboard.
 */
export const paneHeaderActions = cn(
	"flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity duration-fast ease-out",
	"group-hover/pane:opacity-100 group-data-focused/pane:opacity-100",
	"focus-within:opacity-100 has-data-[state=open]:opacity-100",
);

/**
 * The body: the kit's `ScrollArea`, vertical only, under the header and
 * filling the rest of the pane. The whole shell scrolls on the kit's overlay
 * bars: the strip's row sideways, each pane's body up and down.
 */
export const paneBodyScroll = "min-h-0 flex-1";

/**
 * The body's viewport. Vertical only is contained: a wheel that reaches the
 * plane's end stays in it, while a sideways wheel passes on to the strip's
 * row, so the row scrolls from anywhere over a pane. Radix wraps the content
 * in a box of its own; it is made a flex column at least the body's height,
 * so the plane's tail and its click to write reach the bottom.
 */
export const paneBodyViewport =
	"overscroll-y-contain [&>div]:flex! [&>div]:min-h-full [&>div]:flex-col";

/**
 * What the body scrolls: the plane, inside the pane's frame around its
 * grid, gutters included: 12 at the sides (`--spacing-doc-pad-x`), 20 on top
 * and bottom (`--spacing-doc-pad-y`).
 */
export const paneBody =
	"relative flex min-w-0 flex-1 flex-col px-doc-pad-x py-doc-pad-y font-display text-text-primary";

/** A setting's row, on a kit menu item: label on the left, its switch on the right. */
export const paneMenuRow = "gap-3";

export const paneMenuText = "flex min-w-0 flex-1 flex-col";

export const paneMenuLabel = "text-sm text-text-primary";

export const paneMenuHint = "text-xs text-text-muted";

/** The row's switch only shows the state: the row takes the click. */
export const paneMenuSwitch = "pointer-events-none";

/** A choice setting: its label, then its values side by side under it. */
export const paneMenuChoice = "flex flex-col gap-1.5 px-2 pt-1.5 pb-1";

export const paneMenuChoices = "grid grid-cols-3 gap-1";

/**
 * One value of a choice, a menu item drawn as a small tile: its picture over
 * its name. The picked one keeps a quiet fill and a stronger line, like a
 * selected sidebar row; the others are muted until hovered.
 */
export function paneMenuChoiceItem(on: boolean): string {
	return cn(
		"flex-col justify-center gap-1 rounded-md border px-1 py-1.5 text-xs [&_svg]:text-inherit",
		on
			? "border-border-default bg-doc-active text-text-primary"
			: "border-border-subtle text-text-muted",
	);
}

/** The picture in a width tile: a pane outline and the content's lines in it. */
export const paneMenuWidthPicture = "shrink-0";
