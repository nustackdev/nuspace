// Plane icon class recipes: the glyph in its three sizes, and the picker.
//
// An icon is either a lucide glyph from the pack or an emoji, and the two sit
// in the same box at every size: a 16 slot in the rail and on a tab, a 20
// glyph in the picker's 32 cells, and 40 in the gutter beside a plane's title. The emoji is
// text, so it is centred in the box with the line box collapsed, and drawn in
// the platform's colour font (`font-emoji`, tokens.css).
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §Density Popover
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers

import { cn } from "@nustackdev/ui-kit";

import { docGutterTrack } from "./document";

export type IconSize = "sm" | "md" | "lg";

const BOX: Record<IconSize, string> = { sm: "size-4", md: "size-5", lg: "size-10" };

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

/** The emoji are on their way: a small spinner where the grid goes. */
export const iconPickerLoading = "flex justify-center py-8";

/** Nothing matches, or the emoji failed to load. */
export const iconPickerNote = "select-none px-1 py-8 text-center text-sm text-text-muted";

/* ============================== Beside the title ======================== */

/**
 * The icon, a button that opens the picker. It sits in the title row's left
 * gutter (`docTitleRow`), not beside the title's text: a square the gutter's
 * width, its right edge on the content edge the way the cell controls sit,
 * so the title keeps the text edge every cell has. `-my-0.5` centres it on
 * the title's first line (its 2 of pad plus half its 48 line, against half
 * the 56 box) and keeps its height at the title's, so the row is as tall as
 * it would be with no icon. Muted like the rail's; an emoji keeps its own
 * colours.
 */
export const docPlaneIcon = cn(
	docGutterTrack,
	"-my-0.5 flex size-doc-gutter shrink-0 cursor-default items-center justify-center self-start rounded-md text-text-muted",
	"transition-colors duration-fast ease-out hover:bg-doc-hover active:bg-doc-active",
	"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring",
	"data-[state=open]:bg-doc-active",
);

/** A tab's icon, before its title. */
export const tabIcon = "mr-1.5 text-text-muted";
