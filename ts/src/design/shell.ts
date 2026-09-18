// Shell class recipes.
//
// The shell is the frame the two regions hang inside: the sidebar on the left,
// the Viewer claiming the rest. It owns only the frame - how the window splits
// and how each side claims its share.
//
// The window has no strip. The connection pill and the theme flip are the only
// chrome left and they sit in a corner of the window rather than on a bar of
// their own: a 36px rule across the top to carry two controls is more furniture
// than what it holds.
//
// Everything resolves to kit L2/L4 semantic names. No raw hex, nothing off the
// 4px grid.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §1 grid, §4 row heights
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers

import { cn } from "@nustackdev/ui-kit";

/* ============================== the frame ================================ */

/** The window. Owns the viewport height so every region inside can go flex. */
export const shellRoot = "relative flex h-screen bg-bg-canvas text-text-primary";

/** Everything beside the sidebar. */
export const shellMain = "flex min-h-0 min-w-0 flex-1";

/**
 * A full-bleed region. `min-w-0` so a wide child scrolls inside itself instead
 * of pushing the window sideways.
 *
 * Used twice, deliberately the same box: the shell's slot, and the region's own
 * root.
 */
export const shellSurface = "flex min-h-0 min-w-0 flex-1";

/** The window's own chrome, out of the way in the bottom right corner. */
export const shellStatus = cn(
	"pointer-events-none absolute right-2 bottom-2 z-20",
	"flex items-center gap-1 [&>*]:pointer-events-auto",
);

/* ============================== states =================================== */

/** Before the first write lands. Centred, quiet, the whole window. */
export const shellBooting = cn(
	"flex min-h-screen items-center justify-center gap-2",
	"bg-bg-canvas text-base text-text-muted",
);

/** A region the tree does not hold. A fact, not an error, so no tone. */
export const shellMissing = "min-h-0 flex-1 p-6 text-base text-text-muted";
