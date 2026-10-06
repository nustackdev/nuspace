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

/** A row: icon tile, label over description, and the Enter hint when lit. */
export const menuItem = cn(
	commandItemClasses,
	"group w-full gap-3 rounded-md px-2 py-1.5 text-left",
);

/** The icon's tile, so a glyph and an emoji read as the same kind of thing. */
export const menuTile = cn(
	"flex size-9 shrink-0 items-center justify-center rounded-md",
	"border border-border-subtle bg-bg-surface",
	"group-data-[selected=true]:border-border-default group-data-[selected=true]:bg-bg-elevated",
);

export const menuText = "flex min-w-0 flex-1 flex-col";

/** The row's label. Owns the line: it truncates, the hint never does. */
export const menuLabel = "truncate font-medium text-text-primary";

/** The part of the label the query matched. */
export const menuHit = "bg-transparent font-semibold text-accent";

export const menuDescription = "truncate text-xs text-text-muted";

/** The Enter hint on the lit row. */
export const menuEnter = "shrink-0 opacity-0 group-data-[selected=true]:opacity-100";

/** The keys, along the bottom edge. */
export const menuFooter = cn(
	"flex items-center gap-4 border-t border-border-subtle bg-bg-surface px-3 py-2",
	"text-xs text-text-muted",
);

export const menuKey = "flex items-center gap-1.5";
