// Page masthead: class recipes + the banner's generated geometry.
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
//   svg.md        the mark grammar the banner is drawn in: Ref = small
//                 circle (r 4-5), Interaction = small square (side 10-14),
//                 fabric = dashed hairline rect, connectors are straight
//                 lines and right-angle bends only, strokeWidth 1 with
//                 vectorEffect="non-scaling-stroke", rects rx 3, at most one
//                 accent-wash surface per mark.
//   typography.md the page title is the display tier (32/1.2/-0.02), one
//                 step above the document's own h1 (text-3xl), so the
//                 masthead and the body never read as the same heading.
//   space-radius  every number below is on the 4px grid.
//   a11y.md       focus is the kit's one ring recipe (`focus-ring`).
//
// The banner is generated, not uploaded. v1 has no image picker and a stock
// texture would be the one thing direction.md rules out, so the banner is a
// schematic drawn in the SVG vocabulary above, seeded off the page id: the
// same page always draws the same mark, and a different page draws a
// visibly different one. When a real cover picker lands it replaces
// `bannerScene()` and nothing else.
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
export const docBannerMark = "absolute inset-0 h-full w-full";

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

/* ============================== banner geometry ========================== */
//
// Deterministic, not random. A page's mark is a function of its id, so it is
// stable across reloads and distinguishable between pages, and there is no
// frame where the header renders a different picture than it did a second
// ago.

/** FNV-1a. Small, stable, and it does not need to be good, only fixed. */
function hash(seed: string): number {
	let h = 0x811c9dc5;
	for (let i = 0; i < seed.length; i++) {
		h ^= seed.charCodeAt(i);
		h = Math.imul(h, 0x01000193);
	}
	return h >>> 0;
}

/** Deterministic 0..n-1 stream off the seed hash. */
function picker(seed: string): (n: number) => number {
	let state = hash(seed) || 1;
	return (n: number) => {
		state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
		return state % n;
	};
}

export type BannerNode = {
	/** Ref (circle) or Interaction (square), per svg.md §Vocabulary. */
	kind: "ref" | "interaction";
	x: number;
	y: number;
	/** The one lane that carries the accent; everything else is hairline. */
	accent: boolean;
};

export type BannerScene = {
	/** viewBox width/height. Fixed; the banner slices it, never squashes it. */
	width: number;
	height: number;
	/** Horizontal hairline lanes: [y, x0, x1]. */
	lanes: [number, number, number][];
	nodes: BannerNode[];
	/** Right-angle drops between lanes: [x, y0, y1]. */
	drops: [number, number, number][];
	/** The dashed fabric rect: [x, y, w, h]. */
	fabric: [number, number, number, number];
	accentLane: number;
};

const VIEW_W = 1200;
const VIEW_H = 160;
const LANE_Y = [42, 80, 118];
/** Node slots on a 120px pitch. The mark is a schematic, not a sketch. */
const SLOTS = [96, 216, 336, 456, 576, 696, 816, 936, 1056];

/**
 * Build one page's mark.
 *
 * The skeleton is fixed - three lanes, nodes on a fixed pitch, one accent
 * lane, one dashed fabric rect - and only the choices inside it vary. That is
 * on purpose: a fully generated layout is a lottery, and one bad draw is a
 * page that looks broken. This composes a schematic that is always in
 * grammar and merely never the same twice.
 */
export function bannerScene(seed: string): BannerScene {
	const pick = picker(seed || "space");
	const accentLane = pick(3);

	const lanes: [number, number, number][] = LANE_Y.map((y) => {
		const start = pick(3); // 0..2 slots in from the left
		const end = SLOTS.length - 1 - pick(2);
		return [y, SLOTS[start] - 48, SLOTS[end] + 48] as [number, number, number];
	});

	const nodes: BannerNode[] = [];
	for (let lane = 0; lane < LANE_Y.length; lane++) {
		const y = LANE_Y[lane];
		const [, x0, x1] = lanes[lane];
		// 3 or 4 nodes per lane, spread over the lane's own extent.
		const count = 3 + pick(2);
		const step = Math.floor(SLOTS.length / count);
		for (let i = 0; i < count; i++) {
			const x = SLOTS[Math.min(SLOTS.length - 1, i * step + pick(2))];
			if (x < x0 || x > x1) continue;
			if (nodes.some((n) => n.y === y && Math.abs(n.x - x) < 100)) continue;
			nodes.push({
				kind: pick(3) === 0 ? "interaction" : "ref",
				x,
				y,
				accent: lane === accentLane,
			});
		}
	}

	// Two right-angle drops tying adjacent lanes together. Connectors are
	// straight lines and right-angle bends only (svg.md §Vocabulary), so a
	// drop is exactly one vertical segment between two lanes at a shared x.
	const drops: [number, number, number][] = [];
	for (let i = 0; i < 2; i++) {
		const lane = pick(2); // 0->1 or 1->2
		const candidates = nodes.filter((n) => n.y === LANE_Y[lane]);
		if (candidates.length === 0) continue;
		const from = candidates[pick(candidates.length)];
		drops.push([from.x, LANE_Y[lane], LANE_Y[lane + 1]]);
	}

	// The fabric: a dashed hairline rect around a run of the mark. It always
	// encloses at least one full lane so it reads as a container, not a crop.
	const fx = SLOTS[pick(3)] - 56;
	const fw = 360 + pick(3) * 120;
	const fabric: [number, number, number, number] = [
		fx,
		LANE_Y[0] - 22,
		Math.min(fw, VIEW_W - fx - 40),
		LANE_Y[2] - LANE_Y[0] + 44,
	];

	return { width: VIEW_W, height: VIEW_H, lanes, nodes, drops, fabric, accentLane };
}
