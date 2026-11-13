// The registry menus: the `/` menu over a plane and the Add plane popup. Their
// rows, headings and key hints, so the two read as one thing. Each menu keeps
// its own surface (the slash menu's in ./document.ts, the popup is the kit's
// command palette); everything inside it is here.
//
// The rows wear the kit's command palette recipes. A row is lit by
// `data-selected="true"`, whoever sets it (cmdk, or the slash menu itself),
// and carries `group` so what is inside it can follow.
//
// Plus the one width every plane's menu shares.

import { cn, commandHeadingClasses, commandItemClasses } from "@nustackdev/ui-kit";

/**
 * A plane's menu (../menu/PlaneMenuItems.tsx), off a Planes tree row or a
 * pane's header: one width for both, wide enough that a label and its
 * shortcut caps never crowd each other, and narrow enough that a pane
 * setting's hint wraps under its label.
 */
export const planeMenu = "w-64";

/**
 * A package's title: the chevron, its name, how many rows it holds. Not a
 * stop: it only says whether the package is open, and a click lights its
 * first row. Slimmer than an entry's row, so the folds read as the frame.
 */
export const menuPackage = cn(
	"flex w-full cursor-default select-none items-center gap-2 rounded-md px-2 pt-2 pb-1",
	"text-sm font-medium text-text-primary hover:bg-bg-hover",
	"[&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:text-text-secondary",
);

/** The chevron on a package's row, turned while it is open. */
export function menuPackageChevron(open: boolean): string {
	return cn("transition-transform duration-fast ease-out", open && "rotate-90");
}

/** How many rows a package holds, at the row's end. */
export const menuPackageCount = "ml-auto text-xs tabular-nums text-text-muted";

/** A section heading. */
export const menuHeading = cn(commandHeadingClasses, "pt-2 first:pt-1");

/** A row: icon tile, label over description, and the Enter hint when lit. Flat: lit, it only tints. */
export const menuItem = cn(
	commandItemClasses,
	"group w-full items-start gap-3 rounded-md px-2 py-1.5 text-left",
);

/** The icon's tile, so a glyph and an emoji read as the same kind of thing. */
export const menuTile = cn(
	"flex size-9 shrink-0 items-center justify-center rounded-md",
	"border border-border-subtle bg-bg-surface",
);

// Label and description lines are 20px and 16px, the tile's 36px together, so
// a one-line description sits level with the tile. Longer text wraps and the
// row grows: nothing is cut off.

/** The row's text, centered on the tile while it fits beside it. */
export const menuText = "flex min-h-9 min-w-0 flex-1 flex-col justify-center";

/** The row's label. */
export const menuLabel = "break-words font-medium leading-5 text-text-primary";

/** The part of the label the query matched. */
export const menuHit = "bg-transparent font-semibold text-accent-text";

export const menuDescription = "break-words text-xs leading-4 text-text-muted";

/**
 * The Enter hint on the lit row. Its room is kept on every row, only unseen,
 * so lighting a row never rewraps its text. Level with the tile's middle.
 */
export const menuEnter = "invisible mt-2 inline-flex shrink-0 group-data-[selected=true]:visible";

/** The keys, along the bottom edge. */
export const menuFooter = cn(
	"flex items-center gap-4 border-t border-border-subtle bg-bg-surface px-3 py-2",
	"text-xs text-text-muted",
);

export const menuKey = "flex items-center gap-1.5";
