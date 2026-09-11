// Shell class recipes.
//
// The shell is the frame every surface hangs inside: one 36px top strip and
// one full-bleed surface under it. It is chrome, so it is kit chrome - the
// strip's contents are kit primitives and nothing here paints its own hover or
// active state. What the shell owns is only the frame: how tall the strip is,
// which tier it sits on, and how the surface below it claims the rest.
//
// The 36px is the number the rails line up against (`railHeader` uses the same
// h-9), which is what makes the strip and a rail's header read as one rule
// running across the window instead of two.
//
// Everything resolves to kit L2/L4 semantic names. No raw hex, nothing off the
// 4px grid.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §1 grid, §4 row heights
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers

import { cn } from "@nustackdev/ui-kit";

/* ============================== the frame ================================ */

/** The window. Owns the viewport height so every surface inside can go flex. */
export const shellRoot = "flex h-screen flex-col bg-bg-canvas text-text-primary";

/** The top strip. 36px, surface tier, one hairline underneath. */
export const shellStrip = cn(
	"flex h-9 shrink-0 items-center gap-1",
	"border-b border-border-subtle bg-bg-surface px-2",
);

/** The surface switcher inside the strip. */
export const shellNav = "flex items-center gap-1";

/** Everything under the strip. */
export const shellMain = "flex min-h-0 flex-1";

/**
 * A full-bleed surface. `min-w-0` so a wide child scrolls inside itself
 * instead of pushing the window sideways.
 *
 * Used twice per surface, deliberately the same box: the shell's slot, and the
 * surface's own root where it splits into a rail and a canvas.
 */
export const shellSurface = "flex min-h-0 min-w-0 flex-1";

/* ============================== states =================================== */

/** Before the mount envelope lands. Centred, quiet, the whole window. */
export const shellBooting = cn(
	"flex min-h-screen items-center justify-center gap-2",
	"bg-bg-canvas text-base text-text-muted",
);

/** A route with no surface behind it. A fact, not an error, so no tone. */
export const shellMissing = "min-h-0 flex-1 p-6 text-base text-text-muted";
