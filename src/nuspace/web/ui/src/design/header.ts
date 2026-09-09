// Page masthead: class recipes.
//
// A nuspace page opens with a masthead, not a line of text: a decorative
// banner, a page icon that overlaps its bottom edge, the trail that says where
// you are, and the title as a real editable heading. Notion's shape, read
// through this design system rather than through Notion's.
//
// What the design system asks for (go/projects/nustackdev/design/):
//
//   direction.md  hairline chrome, silver-woven color, blueprint not
//                 decoration. "When in doubt, subtract chrome, keep the
//                 frame." No box shadows on containers - flat, hairline
//                 borders carry every edge.
//   svg.md        the grammar the page glyph is drawn in: hairline strokes,
//                 rects rx 3, strokeWidth ~1.25 with
//                 vectorEffect="non-scaling-stroke".
//   typography.md the page title is the display tier (32/1.2/-0.02), one
//                 step above the document's own h1 (text-3xl), so the
//                 masthead and the body never read as the same heading.
//   space-radius  every number below is on the 4px grid.
//   a11y.md       focus is the kit's one ring recipe (`focus-ring`).
//
// The banner is a pattern, not a picture: a dot grid, one accent wash, and a
// fade into the canvas. It is the same on every page. A per-page generated
// schematic was tried and read as noise -- the masthead's job is to frame the
// title, and anything with structure in it competes with the document below.
// When a cover picker lands it replaces the banner's body and nothing else.
//
// Colors here are semantic token names only (`bg-bg-canvas`,
// `border-border-subtle`, `stroke-accent-line`, ...). No hexes, no palette.

import { cn } from "@nustackdev/ui-kit";
import type { CSSProperties } from "react";

/* ============================== masthead shell =========================== */

/**
 * The masthead. Full-bleed across the document surface (the banner is a
 * cover, and a cover that respects the reading measure is a card), with the
 * text content re-centred on the measure inside.
 *
 * The negative bottom margin eats part of the document column's own 64px top
 * pad. Without it the title and the first block sit 64px apart plus the
 * masthead's own trailing space, which reads as two documents rather than
 * one.
 *
 * The `z-10` is load-bearing, not decoration: that same negative margin makes
 * the column's transparent top padding overlap the title, and the column is
 * later in the DOM, so without it the padding eats every click meant for the
 * heading.
 */
export const docMasthead = cn("relative z-10 w-full", "-mb-8");

/** The measure-width text column inside the masthead. */
export const docMastheadColumn = "mx-auto w-full max-w-doc px-doc-pad-x";

/* ============================== banner =================================== */

/**
 * The banner box. 128px is deliberate: tall enough to read as a cover, short
 * enough that the document is still what you see when a page opens.
 *
 * Flat by direction.md - no shadow, no inset highlight. The only edge is the
 * hairline at the bottom, and even that is dissolved by the fade below.
 */
export const docBanner = cn(
	"relative h-32 w-full overflow-hidden",
	"border-b border-border-subtle bg-bg-canvas",
);

/**
 * The dot-grid substrate, exactly the role `.vizFrame` plays on the landing
 * page: the mark sits ON a dotted canvas rather than painting its own dot
 * layer (svg.md §Substrate). 8px pitch matches the document's smallest
 * spacing step.
 */
export const docBannerGridStyle: CSSProperties = {
	backgroundImage: "radial-gradient(var(--border-default) 1px, transparent 1px)",
	backgroundSize: "8px 8px",
	backgroundPosition: "-1px -1px",
};

/**
 * The bottom fade. The banner has to end without a hard horizon, or the page
 * reads as a header pasted on top of a document instead of one surface. A
 * gradient into `--bg-canvas` is the cheapest way to say that, and it is a
 * token, not a color.
 */
export const docBannerFadeStyle: CSSProperties = {
	backgroundImage: "linear-gradient(to bottom, transparent 45%, var(--bg-canvas) 100%)",
};

/** The generated mark itself, stretched across the banner. */

/** Absolute layer helper for the substrate / wash / fade stack. */
export const docBannerLayer = "pointer-events-none absolute inset-0";

/**
 * The single accent-wash surface the mark is allowed (svg.md §Palette). Kept
 * in CSS rather than in the SVG so the mark itself stays pure geometry.
 */
export const docBannerWashStyle: CSSProperties = {
	backgroundImage: "radial-gradient(120% 140% at 12% 0%, var(--accent-wash) 0%, transparent 62%)",
};

/** The breadcrumb rides on the banner, aligned to the reading measure. */
export const docBannerTrail = cn(
	"absolute inset-x-0 top-4 z-10",
	docMastheadColumn,
	"pointer-events-auto",
);

/* ============================== page icon ================================ */

/**
 * The icon frame. 56px, overlapping the banner's bottom edge by half its
 * height, which is what ties the two together - a frame sitting fully below
 * the banner is a second element, one that straddles it is a masthead.
 *
 * Flat: elevated surface plus a hairline, no shadow. The 4px canvas-colored
 * ring is not elevation, it is the cut that keeps the frame legible where it
 * crosses the banner's own hairline.
 */
export const docPageIcon = cn(
	"relative -mt-7 mb-3 flex size-14 items-center justify-center",
	"rounded-lg border border-border-default bg-bg-elevated",
	"ring-4 ring-bg-canvas",
	"text-text-secondary",
);

/** The glyph inside the frame. Hairline, same grammar as the banner. */
export const docPageIconGlyph = "size-7";

/* ============================== title ==================================== */

/**
 * The editable title. It is an `h1` with `contenteditable`, not an input and
 * not a button: the heading you read and the heading you type are the same
 * node, so there is no mode swap and no layout shift on click.
 *
 * The placeholder is a `::before` on the empty element rather than a second
 * absolutely positioned node, so it can never fall out of alignment with the
 * caret.
 */
export const docTitle = cn(
	"focus-ring -mx-1 block w-[calc(100%+0.5rem)] rounded-sm px-1 py-0.5",
	"cursor-text whitespace-pre-wrap break-words outline-none",
	"empty:before:pointer-events-none empty:before:text-text-muted",
	"empty:before:content-[attr(data-placeholder)]",
);
