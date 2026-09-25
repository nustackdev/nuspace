// Plane icon class recipes: the glyph in its three sizes, and the picker.
//
// An icon is either a lucide glyph from the pack or an emoji, and the two sit
// in the same box at every size: a 16 slot in the rail and on a tab, a 20
// glyph in the picker's 32 cells, and 44 over a plane's title. The emoji is
// text, so it is centred in the box with the line box collapsed, and drawn in
// the platform's colour font (`font-emoji`, tokens.css).
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §Density Popover
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers

import { cn } from "@nustackdev/ui-kit";

export type IconSize = "sm" | "md" | "lg";

const BOX: Record<IconSize, string> = { sm: "size-4", md: "size-5", lg: "size-11" };

/** A lucide glyph at `size`, plus the caller's classes. */
export function iconGlyph(size: IconSize, className?: string): string {
	return cn("shrink-0", BOX[size], className);
}

const EMOJI_TEXT: Record<IconSize, string> = { sm: "text-lg", md: "text-2xl", lg: "" };

/**
 * An emoji in the same box a glyph of `size` takes, plus the caller's
 * classes. The large size is the `text-plane-icon` token, appended after
 * `cn` for the reason `docTitle` gives: tailwind-merge reads a custom size as
 * a colour and drops it next to a real one.
 */
export function iconEmoji(size: IconSize, className?: string): string {
	const base = cn(
		"inline-flex shrink-0 select-none items-center justify-center overflow-visible",
		"font-emoji leading-none",
		BOX[size],
		EMOJI_TEXT[size],
		className,
	);
	return size === "lg" ? `${base} text-plane-icon` : base;
}

/* ============================== Picker ================================== */

/** The popover. Nine 32px cells a row, and no pad of its own: its parts pad. */
export const iconPicker = "flex w-82 flex-col p-0";

/** Tabs on the left, "Remove" on the right. */
export const iconPickerHead = "flex items-center justify-between gap-2 px-2 pt-1";

export const iconPickerRemove = "text-text-muted hover:text-text-primary";

export const iconPickerSearch = "px-2 pt-2 pb-1";

/** The scrolling body. Tall enough for a few groups, never the whole screen. */
export const iconPickerBody = "h-72 overflow-y-auto overflow-x-hidden px-2 pb-2";

/** A group's name over its cells. */
export const iconPickerGroup = "select-none px-1 pt-2 pb-1 text-xs text-text-muted";

export const iconPickerRow = "grid grid-cols-9 gap-0.5";

/**
 * One cell. The plane's current icon keeps a quiet fill; hover and keyboard
 * focus share the neutral tier, so the grid never lights up in the accent.
 */
export function iconPickerCell(current: boolean): string {
	return cn(
		"flex size-8 cursor-default items-center justify-center rounded-md text-text-secondary",
		"transition-colors duration-fast ease-out",
		"hover:bg-doc-hover hover:text-text-primary",
		"focus-visible:bg-doc-active focus-visible:text-text-primary focus-visible:outline-hidden",
		"focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
		current && "bg-doc-active text-text-primary",
	);
}

/** Nothing matches, the emoji are loading, or they failed to. */
export const iconPickerNote = "select-none px-1 py-8 text-center text-sm text-text-muted";

/* ============================== Over the title ========================== */

/**
 * The icon and the title as one block, and the `head` group its "Add icon"
 * listens to. It carries the run-up the title used to, less the icon lane,
 * so with no icon the title does not move.
 */
export function docTitleBlock(compact = false): string {
	return cn(
		"group/head relative",
		compact ? "mt-0" : "mt-[calc(var(--spacing-doc-title-gap)_-_var(--spacing-doc-icon-lane))]",
	);
}

/** The lane over the title "Add icon" sits in, on the title's left edge. */
export const docIconLane = "flex h-doc-icon-lane items-start px-doc-cell-x";

/** "Add icon": out of sight until the title block is hovered or it has focus. */
export const docAddIcon = cn(
	"-ml-2 text-text-muted hover:text-text-primary",
	"opacity-0 transition-opacity duration-fast ease-out",
	"group-hover/head:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100",
);

/** The set icon, a button that opens the picker. Its glyph on the title's edge. */
export const docPlaneIcon = cn(
	"mb-1 ml-0.5 flex size-14 cursor-default items-center justify-center rounded-md text-text-secondary",
	"transition-colors duration-fast ease-out hover:bg-doc-hover active:bg-doc-active",
	"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring",
);

/** A tab's icon, before its title. */
export const tabIcon = "mr-1.5 text-text-muted";
