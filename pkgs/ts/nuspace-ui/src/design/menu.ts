// The registry menus: the `/` menu over a plane and the Add plane popup. Their
// rows, headings and key hints, so the two read as one thing. Each menu keeps
// its own surface (the slash menu's in ./document.ts, the popup is the kit's
// command palette); everything inside it is here.
//
// The rows wear the kit's command palette recipes. A row is lit by
// `data-selected="true"`, whoever sets it (cmdk, or the slash menu itself),
// and carries `group` so what is inside it can follow.

import { cn, commandHeadingClasses, commandItemClasses } from "@nustackdev/ui-kit";

/** A section heading. */
export const menuHeading = cn(commandHeadingClasses, "pt-2 first:pt-1");

/** A row: icon tile, label over description, and the Enter hint when lit. Lit, it lifts as its float does. */
export const menuItem = cn(
	commandItemClasses,
	"group w-full gap-3 rounded-md px-2 py-1.5 text-left data-[selected=true]:shadow-raised",
);

/** The icon's tile, so a glyph and an emoji read as the same kind of thing. */
export const menuTile = cn(
	"flex size-9 shrink-0 items-center justify-center rounded-md",
	"border border-border-subtle bg-bg-surface",
	"group-data-[selected=true]:border-border-default group-data-[selected=true]:bg-bg-elevated",
);

export const menuText = "flex min-w-0 flex-1 flex-col";

// Label and description lines are 20px and 16px, the tile's 36px together, so
// a row's tile, text and hint sit at the same offsets whether centered (the
// row) or from the top (its float): lighting a row moves nothing in it.

/** The row's label. Owns the line: it truncates, the hint never does. */
export const menuLabel = "truncate font-medium leading-5 text-text-primary";

/** The part of the label the query matched. */
export const menuHit = "bg-transparent font-semibold text-accent-text";

export const menuDescription = "truncate text-xs leading-4 text-text-muted";

/**
 * The lit row whole, when its row cut it off: drawn over the row and the rows
 * under it, so nothing in the list moves. Lined up with the row it covers
 * (same padding and gap), opaque under the hover tint, and blind to the
 * pointer so the rows beneath still take hover.
 */
export const menuFloat = cn(
	"pointer-events-none absolute inset-x-0 top-0 z-10 hidden group-data-[selected=true]:block",
	"rounded-md bg-bg-elevated shadow-raised",
);

export const menuFloatRow = "flex items-start gap-3 rounded-md bg-bg-hover px-2 py-1.5";

/** The labels in the float, wrapping instead of truncating. */
export const menuFloatLabel = "break-words font-medium leading-5 text-text-primary";

export const menuFloatDescription = "break-words text-xs leading-4 text-text-muted";

/**
 * The Enter hint on the lit row. Out of the layout elsewhere, so it leaves no
 * gap. Pinned to the middle of the first 36px, so the float's sits where the row's did.
 */
export const menuEnter = "mt-2 hidden shrink-0 self-start group-data-[selected=true]:inline-flex";

/** The keys, along the bottom edge. */
export const menuFooter = cn(
	"flex items-center gap-4 border-t border-border-subtle bg-bg-surface px-3 py-2",
	"text-xs text-text-muted",
);

export const menuKey = "flex items-center gap-1.5";
