// Pane class recipes: the bar across a pane's top and the settings menu off
// its `...`.
//
// The bar is window chrome, not document: it stays put while the plane under it
// scrolls, and it is quiet enough that a single pane still reads as a plane
// with nothing around it. No border, a muted title, ghost buttons. It only
// draws over a lone pane: a split gets the tab bar (./tabs.ts) instead.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §4 row heights
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers

import { cn } from "@nustackdev/ui-kit";

/**
 * The bar. `h-chrome`, like the rail's header strip, so the two tops line up.
 * With the rail collapsed the reopen button sits over its left end, so the
 * title steps right past it.
 */
export const paneBar = cn(
	"flex h-chrome shrink-0 items-center gap-0.5",
	"bg-bg-canvas pl-4 pr-1.5 group-data-[rail=collapsed]/main:pl-12",
);

/**
 * The bar's title, muted. The bar only draws over a lone pane (a split gets
 * the tab bar instead), so there is no focused title to bring up a tier.
 */
export const paneBarTitle = cn("min-w-0 flex-1 select-none truncate text-sm", "text-text-muted");

/** The bar's two buttons: the kit's ghost `sm`, a tier back until hovered. */
export const paneBarButton = "text-text-muted hover:text-text-primary";

/** The settings popover. Narrow, and a list rather than a padded card. */
export const paneMenu = "w-64 p-1";

/** A plain action row, above the settings (Rename, off a tab). */
export const paneMenuAction = cn(
	"flex h-8 w-full cursor-default select-none items-center rounded-md px-2",
	"text-left text-sm text-text-primary",
	"transition-colors duration-fast ease-out hover:bg-doc-hover",
	"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
);

/** The hairline between the actions and the settings. */
export const paneMenuSeparator = "-mx-1 my-1 h-px bg-border-subtle";

/** A setting's row: label on the left, its control on the right. */
export const paneMenuRow = cn(
	"flex min-h-8 w-full cursor-default select-none items-center gap-3",
	"rounded-md px-2 py-1.5",
	"transition-colors duration-fast ease-out hover:bg-doc-hover",
);

export const paneMenuText = "flex min-w-0 flex-1 flex-col";

export const paneMenuLabel = "text-sm text-text-primary";

export const paneMenuHint = "text-xs text-text-muted";
