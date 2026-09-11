// Lens-surface class recipes.
//
// Same job design/document.ts does for the editor: the component never picks
// a token at the call site, so the whole surface can be re-tuned here without
// touching lens.tsx, and we do not end up with forty one-off className strings.
//
// Everything resolves to kit L2/L4 semantic names or to the lens-* / doc-*
// names declared in ./lens.css and ./tokens.css. No raw hex, no arbitrary
// values off the 4px grid.
//
// The kind / value-type vocabulary these helpers switch on is wire vocabulary
// (`entry.kind`, `entry.vtype`) and lives with the ref, in
// refs/lens/types.ts. What is left here takes a type name and returns a class
// string, which is the only thing the design layer is allowed to know about it.

import { cn } from "@nustackdev/ui-kit";

/* ============================== tone ===================================== */

/**
 * Glyph color. Two channels, deliberately: the GLYPH says what type it is,
 * the COLOR says only whether the row goes anywhere. Painting five kinds in
 * five categorical hues turns a 200-row column into confetti and, per
 * a11y.md §7, leans on color as the sole carrier of a distinction the glyph
 * is already making. So: navigable rows take the blue secondary, terminal
 * rows stay muted, and only a genuinely bad state (invalid, error) earns a
 * status hue.
 */
export function glyphTone(vtype: string, navigable: boolean): string {
	if (vtype === "invalid" || vtype === "error") return "text-status-danger";
	if (vtype === "empty" || vtype === "none") return "text-text-muted";
	return navigable ? "text-accent-2" : "text-text-muted";
}

/**
 * The trailing value cell's type tier.
 *
 * `ref` is a type tag (`StrRef`, `DictRef`) rather than a value, so it sits
 * one tier quieter than a real value and never competes with the key.
 */
export function valueTone(vtype: string): string {
	switch (vtype) {
		case "int":
		case "float":
			return "text-accent-2 tabular-nums";
		case "bool":
			return "text-accent";
		case "str":
			return "text-text-secondary";
		case "invalid":
		case "error":
			return "text-status-danger";
		case "none":
		case "empty":
			return "text-text-muted";
		case "ref":
			return "text-text-muted";
		default:
			return "text-text-secondary";
	}
}

/** Sentinel and null render as a word in a dashed hairline chip, not as text.
 *  "nothing is here" is a state, and a state should look like a chip. */
export const lensSentinelChip = cn(
	"inline-flex items-center rounded-sm border border-dashed px-1",
	"font-mono text-xs leading-none",
);

/* ============================== surface ================================== */

/** The whole lens. Full-bleed: it IS the surface, not a card sitting on one. */
export const lensRoot = cn(
	// flex-1 because the shell mounts a field straight into a flex row with no
	// wrapper of its own; without it the lens shrink-to-fits its widest column
	// and leaves the rest of the surface blank.
	"flex h-full min-h-0 w-full min-w-0 flex-1 flex-col",
	"bg-bg-canvas text-text-primary",
);

/**
 * The toolbar above the columns. 32px, the kit's default control row, and the
 * same `bg-bg-surface` + hairline the shell's top strip uses - so the two
 * strips stack into one piece of chrome instead of reading as two widgets.
 */
export const lensBar = cn(
	"flex h-lens-bar shrink-0 items-center gap-3",
	"border-b border-border-subtle bg-bg-surface px-2",
);

/** The path trail. Scrolls sideways on its own; never pushes the hint off. */
export const lensBarPath = cn(
	"flex min-w-0 flex-1 items-center overflow-x-auto",
	"[scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
);

/** The keyboard legend. Shrink-0 so a deep path never eats it. */
export const lensBarHint = cn(
	"flex shrink-0 items-center gap-1.5 text-xs text-text-muted select-none",
);

/** One "key does thing" pair inside the legend. */
export const lensHintPair = "flex items-center gap-1";

/** Crumb type: mono, because every segment is a real key in the store. */
export const lensCrumb = "font-mono text-sm whitespace-nowrap";

/* ============================== columns ================================== */

/** The scroll host for the columns. Horizontal only; each column scrolls Y. */
export const lensColumns = cn(
	"flex min-h-0 flex-1 overflow-x-auto overflow-y-hidden outline-none",
	// the container owns the keyboard, so it owns the focus ring - but drawn
	// as an inset line, not a halo, so it never overlaps the first column.
	"focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-inset",
);

/** One column. A unit: its own vertical rule, its own header, its own scroll. */
export function lensColumn(leaf: boolean): string {
	return cn(
		"flex min-h-0 shrink-0 flex-col border-r border-lens-rule bg-lens-body",
		leaf ? "w-lens-col-leaf" : "w-lens-col",
	);
}

/**
 * The column's lid. Sits on the surface tier so the column reads as a stack
 * of rows under a header rather than as a loose run of text. The live column
 * swaps the hairline for a 2px accent underline - the cheapest possible "the
 * keyboard is in this one" marker, and it survives at a glance across eight
 * columns where a row-level cue would not.
 */
export function lensColumnHead(active: boolean): string {
	return cn(
		"flex h-lens-head shrink-0 items-center gap-1.5 px-2",
		"bg-lens-head text-xs text-text-muted select-none",
		"border-b-2",
		active ? "border-b-lens-head-active-line" : "border-b-lens-rule",
	);
}

/** Kind label inside the column head. */
export const lensColumnKind = "font-medium tracking-[0.02em] uppercase";

/** Row count, pushed to the right edge of the head. */
export const lensColumnCount = "ml-auto font-mono tabular-nums";

/**
 * The pane past the last column. A column browser that just stops halfway
 * across the screen reads as a broken layout; carrying the header rule and
 * the body tier to the right edge makes the surface read as one grid the
 * columns are filling in. It also gives the container's focus ring something
 * to hug instead of boxing empty canvas.
 */
export const lensFiller = cn("flex min-h-0 flex-1 flex-col bg-lens-body", "min-w-lens-col");

/** The filler's lid, so the header rule runs edge to edge. */
export const lensFillerHead = cn("h-lens-head shrink-0 border-b-2 border-b-lens-rule bg-lens-head");

/** The rows. Scrolls independently, thin gutter so 200 rows stay scannable. */
export const lensColumnBody = "min-h-0 flex-1 overflow-y-auto overflow-x-hidden";

/* ============================== rows ===================================== */

export interface RowState {
	/** The keyboard cursor. Exactly one on the surface, in the live column. */
	cursor?: boolean;
	/** This row opened the column to its right. One per non-live column. */
	trail?: boolean;
}

/**
 * One row. 24px, mono, no vertical padding - the row height IS the rhythm.
 *
 * Three tiers, and they must not collapse into each other (see lens.css for
 * why): hover is NEUTRAL, the trail is a stronger NEUTRAL, and only the live
 * cursor is accent. A 2px left rail doubles the cursor/trail distinction so
 * it survives without color, per a11y.md §7.
 */
export function lensRow(state: RowState = {}): string {
	return cn(
		"group/row relative flex h-lens-row w-full items-center gap-1.5",
		// the rail lives in the first 8px; text starts after it either way, so
		// nothing shifts when a row becomes the cursor.
		"pr-2 pl-2 text-left font-mono text-sm outline-none",
		"transition-colors duration-fast ease-out",
		!state.cursor && !state.trail && "text-text-secondary hover:bg-doc-hover",
		state.trail && "bg-lens-trail text-text-primary",
		state.cursor && "bg-lens-cursor text-text-primary",
		"active:bg-doc-active",
		// the container owns the focus ring; a per-row halo on a keyboard walk
		// through 200 rows is noise.
		"focus-visible:outline-none",
	);
}

/** The 2px rail marking cursor / trail. Same slot, different tier. */
export function lensRowRail(state: RowState): string {
	if (!state.cursor && !state.trail) return "hidden";
	return cn(
		"absolute top-0 bottom-0 left-0 w-lens-rail",
		state.cursor ? "bg-lens-cursor-line" : "bg-lens-trail-line",
	);
}

/** The type glyph. 12px, aligned to the mono baseline. */
export const lensRowGlyph = "size-3 shrink-0";

/** The key. Owns the row: it truncates last and never dims. */
export const lensRowKey = "min-w-0 flex-1 truncate";

/** The trailing value / type tag. Gives up space to the key first. */
export const lensRowValue = cn(
	"max-w-[55%] shrink truncate text-right text-xs",
	// a value is context, not the row's subject: it fades back until the row
	// is the cursor or the trail, where the whole row steps forward.
	"opacity-80 group-hover/row:opacity-100",
);

/** The "goes somewhere" chevron. Reserved width, so keys align across rows. */
export function lensRowChevron(navigable: boolean): string {
	return cn("size-3 shrink-0", navigable ? "text-text-muted" : "invisible");
}

/* ============================== leaf column ============================== */

/**
 * The leaf column does not render rows. A leaf is one value, and a value that
 * is 3kB of python source has nothing to do with a 24px cell - so the leaf
 * column drops the row grammar entirely and becomes a reader: wrapped mono,
 * its own scroll, the type stated once in the header.
 */
export const lensLeafBody = cn(
	"min-h-0 flex-1 overflow-auto p-3",
	"font-mono text-sm leading-relaxed whitespace-pre-wrap break-words",
);

/** Note under a clipped value. */
export const lensLeafNote = cn(
	"shrink-0 border-t border-lens-rule px-3 py-1",
	"text-xs text-text-muted select-none",
);

/* ============================== states =================================== */

/** A column with nothing in it. Centred, quiet, says which nothing it is. */
export const lensEmpty = cn(
	"flex flex-1 flex-col items-center justify-center gap-1.5 px-3 py-6",
	"text-center text-xs text-text-muted select-none",
);

/** Footer on a capped column. The cap is a fact about the view, not an error. */
export const lensCapNote = cn(
	"shrink-0 border-t border-lens-rule px-2 py-1",
	"font-mono text-xs text-text-muted select-none",
);

/** One skeleton row, sized to the real row so nothing jumps when data lands. */
export const lensSkeletonRow = "flex h-lens-row items-center gap-1.5 px-2";
