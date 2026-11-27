// Plane icon class recipes: the button beside the title, and a tab's icon.
//
// The icon itself is the kit's `IconMark`, and the picker the kit's
// `IconPickerContent`; what is left here is where nuspace puts them.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers

import { cn } from "@nustackdev/ui-kit";

/* ============================== Beside the title ======================== */

/**
 * The icon, a button that opens the picker. It sits on the content edge, in
 * the title's line (`docTitleLine`), not out in the gutter: the 32 glyph in
 * a 40 square, so with the square's 4 of pad the glyph starts on the text
 * edge every cell has, and the title follows it. `mt-px` centres it on the
 * title's first line. Muted like the rail's; an emoji keeps its own colours.
 */
export const docPlaneIcon = cn(
	"mt-px flex size-10 shrink-0 cursor-default items-center justify-center self-start rounded-md text-text-muted",
	"transition-colors duration-fast ease-out hover:bg-doc-hover active:bg-doc-active",
	"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring",
	"data-[state=open]:bg-doc-active",
);

/** A tab's icon, before its title. */
export const tabIcon = "mr-1.5 text-text-muted";
