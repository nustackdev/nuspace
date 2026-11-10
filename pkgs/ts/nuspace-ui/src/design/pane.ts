// Pane class recipes: the bar across a pane's top and the settings menu off
// its `...`, a kit dropdown.
//
// The bar is window chrome, not document: it stays put while the plane under it
// scrolls, and it is quiet enough that a single pane still reads as a plane
// with nothing around it. No border, a muted title, the kit's ghost buttons.
// Every pane on the desk has one, so a title always scrolls with its pane.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §4 row heights
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers

import { cn } from "@nustackdev/ui-kit";

/**
 * The bar. `h-chrome`, like the rail's header strip, so the two tops line up.
 * Transparent, so the pane's own surface (canvas, or sunken when dimmed)
 * shows through. With the rail collapsed the reopen button sits over the
 * desk's left end, so the first pane's title steps right past it. With more
 * than one pane the bar is the handle a pane is dragged along the desk by.
 */
export function paneBar(first: boolean, movable: boolean): string {
	return cn(
		"flex h-chrome shrink-0 items-center gap-0.5 bg-transparent pl-4 pr-1.5",
		first && "group-data-[rail=collapsed]/main:pl-12",
		movable && "cursor-grab active:cursor-grabbing",
	);
}

/**
 * The bar's trail: the planes above this one, then its own title, on the
 * kit's breadcrumb. One line, filling the bar up to its buttons.
 */
export const paneCrumbs = "min-w-0 flex-1";

export const paneCrumbList = "min-w-0 flex-nowrap gap-1";

/**
 * A parent's crumb, and the `...` for the ones collapsed. They give way
 * first when the pane is narrow, so the plane's own title is the last to
 * truncate.
 */
export const paneCrumbParent = "min-w-0 shrink-[8]";

/** A parent's link. Muted like the title, up a tier on hover. */
export const paneCrumbLink = "block truncate text-text-muted hover:text-text-primary";

export const paneCrumbSep = "shrink-0";

/** The plane's own crumb, the last one. */
export const paneCrumbHere = "min-w-0";

/**
 * The bar's title, the plane's own crumb. Muted, and a tier up on the
 * focused pane when the desk holds more than one, so the focus reads in the
 * title as well as the surface.
 */
export function paneBarTitle(lit: boolean): string {
	return cn(
		"block min-w-0 select-none truncate font-normal",
		lit ? "text-text-primary" : "text-text-muted",
	);
}

/** A setting's row, on a kit menu item: label on the left, its switch on the right. */
export const paneMenuRow = "gap-3";

export const paneMenuText = "flex min-w-0 flex-1 flex-col";

export const paneMenuLabel = "text-sm text-text-primary";

export const paneMenuHint = "text-xs text-text-muted";

/** The row's switch only shows the state: the row takes the click. */
export const paneMenuSwitch = "pointer-events-none";
