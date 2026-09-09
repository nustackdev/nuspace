// Document-surface class recipes.
//
// The editor shell is written from zero (task-139 part 2), but its *styling*
// is not. These are the recipes every block, gutter, handle and menu reaches
// for, so the shell never picks a token at the call site and we do not end up
// with forty one-off className strings that have to be unwound later.
//
// Everything below resolves to kit L2/L4 semantic names or the doc-* /
// section-* names declared in ./tokens.css. No raw hex, no arbitrary values
// off the 4px grid.
//
// Density note. A document is not a panel. Horizontally it uses kit density
// (a block's inner chrome is chrome: 32px rows, 6px radii). Vertically it is
// looser, but the air comes from the 16px/1.55 prose line box, not from
// padding - block padding stays at 4px. See tokens.css for the full rule.

import { cn } from "@nustackdev/ui-kit";

import type { SectionStatus } from "./section-status";
import { hasGutterRail } from "./section-status";

/* ============================== page + column ============================ */

/** Outer scroll surface. Canvas, not surface: the page IS the background. */
export const docPage = cn(
	"relative h-full w-full overflow-y-auto overflow-x-hidden",
	"bg-bg-canvas text-text-primary font-display",
);

/**
 * The reading column. Blocks sit inside; the gutter hangs off the left edge
 * into the page padding, which is why pad-x is doc-pad-x and not zero.
 */
export const docColumn = cn(
	"relative mx-auto w-full max-w-doc",
	"px-doc-pad-x pt-doc-pad-y pb-doc-pad-y",
	"flex flex-col gap-doc-block-gap",
);

/** A program block that opts out of the reading measure (charts, tables). */
export const docColumnWide = cn(docColumn, "max-w-doc-wide");

/** Document body type tier. 16px is the only place typography.md ships xl. */
export const docProse = "text-xl text-text-primary";

/** Code inside a block. Editor tier is 14px mono, per typography.md §1. */
export const docCode = "font-mono text-lg text-text-primary";

/* ============================== prose interior =========================== */
//
// The inside of a prose island. These are the *only* place the document's
// typographic rhythm is stated, and the editor's schema hands them straight
// to `toDOM`, so what you type is styled by the same recipe that styles what
// you read. That is what removes the old leaf's mode-swap layout shift:
// there is no second rendering to disagree with.

/** The contenteditable host itself. */
export const docProseEditor = cn(docProse, "nu-prose outline-none");

/** A paragraph. Tight vertical rhythm; the air comes from the line box. */
export const docParagraph = "my-2 leading-relaxed first:mt-0 last:mb-0";

/** Headings. Only three levels; the slash menu offers exactly these. */
export function docHeading(level: number): string {
	return (
		{
			1: "text-3xl font-semibold tracking-tight mt-6 mb-2 first:mt-0",
			2: "text-2xl font-semibold tracking-tight mt-5 mb-2 first:mt-0",
			3: "text-xl font-semibold tracking-tight mt-4 mb-1.5 first:mt-0",
		}[level] ?? "text-xl font-semibold tracking-tight mt-4 mb-1.5 first:mt-0"
	);
}

export const docBlockquote = cn(
	"my-2 border-l-2 border-border-strong pl-3 text-text-secondary",
	"[&>p]:my-1 [&>p:first-child]:mt-0 [&>p:last-child]:mb-0",
);

const LIST = cn("my-2 space-y-1 pl-5 marker:text-text-muted", "[&_ul]:my-1 [&_ol]:my-1");
export const docBulletList = cn(LIST, "list-disc");
export const docOrderedList = cn(LIST, "list-decimal");

/** A list item. Its paragraph loses the block margin so items stay tight. */
export const docListItem = "[&>p]:my-0";

export const docRule = "my-5 border-border-subtle";

/* --- inline marks --- */

export const docStrong = "font-semibold";
export const docEm = "italic";
export const docInlineCode = cn(
	"rounded-sm bg-bg-sunken px-1 py-0.5",
	"font-mono text-[0.9em] text-text-primary",
);
export const docLink = "text-accent underline underline-offset-2";

/* ============================== block ==================================== */

export interface BlockStateFlags {
	/** The caret lives in this block. No fill, gutter rail only. */
	focused?: boolean;
	/** Block-level selection (across an island boundary). Accent fill. */
	selected?: boolean;
	/** Part of a multi-block selection. Stronger accent fill. */
	selectedStrong?: boolean;
	/** This block is the one being dragged. Ghosted while it travels. */
	dragging?: boolean;
	/** Program block rather than a prose island. Slightly more pad-y. */
	program?: boolean;
}

/**
 * One block. The content flows normally at full measure; the gutter is hung
 * outside the block's left edge (see `docGutter`), so nothing the gutter
 * renders can shift the reading column.
 *
 * Hover and pressed are NEUTRAL (doc-hover / doc-active); selection is the
 * accent tier. That split is deliberate - on a document, hovering every
 * paragraph in purple would make hover indistinguishable from selection.
 *
 * The block does NOT tint on its own hover. Reading is the primary act on
 * this surface and the pointer crosses every block on the way to anywhere,
 * so a fill that follows the cursor down the page is noise against the one
 * thing the reader is trying to do. The tint is scoped to the drag handle
 * instead: it fires when the pointer is on the affordance that acts on the
 * whole block, which is the only moment "this block" is the unit you mean.
 * `:has()` rather than a React hover flag, because tracking pointer-enter
 * per block would rerender the document on every mouse move.
 */
export function docBlock(state: BlockStateFlags = {}): string {
	return cn(
		"group/block relative w-full rounded-sm",
		"px-doc-block-x",
		state.program ? "py-doc-block-y-program" : "py-doc-block-y",
		"transition-colors duration-fast ease-out",
		!state.selected && "has-[[data-block-grip]:hover]:bg-doc-hover",
		state.selected && "bg-doc-selected",
		state.selectedStrong && "bg-doc-selected-strong",
		// the caret's block gets no fill: it is already marked by the caret.
		// It gets the neutral gutter rail instead, see `docFocusRail`.
		state.focused && "z-10",
		state.dragging && "opacity-40",
	);
}

/**
 * Neutral rail marking the block the caret is in. Sits in the same slot as
 * the status rail; status wins when both apply, since a failing block is
 * more urgent than "you are here".
 */
export const docFocusRail = cn(
	"absolute left-0 top-0 bottom-0 w-doc-rail rounded-full",
	"bg-doc-focus-rail",
);

/**
 * The gutter. Hangs off the block's left edge into the page padding and holds
 * the block's affordances: add, drag. Affordances are hidden at rest and
 * revealed on block hover or keyboard focus - a document at rest shows text,
 * not controls.
 *
 * Sized to hold exactly two `sm` IconButtons (24px each + a 2px gap), which is
 * what makes the gutter one lane instead of two overlapping ones. The top
 * offset centres that 24px row on the block's *first line*, which is a 25px
 * prose line box on an island and the 32px control row a program block opens
 * with - so the handles line up with the text either way.
 */
export function docGutter(program = false): string {
	return cn(
		"absolute right-full w-doc-gutter",
		program ? "top-3" : "top-1",
		"flex items-center justify-end gap-0.5 pr-1 select-none",
	);
}

/**
 * Wrapper for the hover-only affordances inside the gutter. One row, one
 * reveal, so add and drag read as a pair rather than as two loose glyphs.
 */
export const docGutterAffordances = cn(
	"flex items-center gap-0.5",
	"opacity-0 transition-opacity duration-fast ease-out",
	"group-hover/block:opacity-100 group-focus-within/block:opacity-100",
	// keep them visible while a menu they opened is still open
	"[&:has([data-state=open])]:opacity-100",
);

/**
 * Extra classes for the drag handle on top of a kit `IconButton ghost sm`.
 * Only the grab cursor is ours; the box, the hover and the focus ring are the
 * kit's, which is what keeps the gutter aligned with every other control.
 */
export const docDragHandle = "cursor-grab active:cursor-grabbing";

/** Drop indicator drawn between two blocks during a drag. 2px accent line. */
export const docDropIndicator = cn(
	"pointer-events-none absolute inset-x-0 h-doc-rail -translate-y-1/2",
	"rounded-full bg-doc-drop-line",
);

/* ============================== status ================================== */

/**
 * The status rail: a 2px line down the left of the block, in the section's
 * hue. Only painted for states that want the author's eye - see
 * `hasGutterRail`. Everything else stays silent.
 */
export function docStatusRail(status: SectionStatus): string {
	if (!hasGutterRail(status)) return "hidden";
	return cn(
		"absolute left-0 top-0 bottom-0 w-doc-rail rounded-full",
		"transition-colors duration-fast ease-out",
		{
			invalid: "bg-section-invalid",
			failed: "bg-section-failed",
			running: "bg-section-running",
		}[status as "invalid" | "failed" | "running"],
	);
}

/**
 * The traceback / diagnostic body inside a block's status panel. The panel
 * itself is the kit's `Alert` (it already owns the wash, the line, the tone
 * icon and `role="alert"`); all that is left for the document layer is the
 * fact that a python traceback is preformatted text and has to be able to
 * scroll sideways without widening the reading column.
 */
export const docStatusTrace = cn(
	"font-mono text-sm whitespace-pre-wrap break-words",
	"max-h-64 overflow-auto",
);

/* ============================== slash menu =============================== */

/**
 * Slash menu surface. Same surface grammar as a kit DropdownMenu (elevated,
 * default border, lg radius) so it does not read as a foreign widget on a
 * page that also hosts kit primitives.
 */
export const docSlashMenu = cn(
	"z-50 min-w-56 max-h-80 overflow-y-auto",
	"rounded-lg border border-border-default bg-bg-elevated",
	"p-1 shadow-lg",
	"data-[state=open]:animate-in data-[state=open]:fade-in-0",
	"data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
	"duration-base ease-out",
);

/** Group heading inside the slash menu. */
export const docSlashMenuLabel = cn(
	"px-2 py-1.5 text-xs font-medium tracking-[0.02em]",
	"uppercase text-text-muted select-none",
);

/**
 * One slash-menu row. 32px, the kit's default row height. Active row uses the
 * accent tier because here selection IS the only state - there is no
 * competing hover semantic inside a menu.
 */
export const docSlashMenuItem = cn(
	"flex h-8 w-full cursor-default select-none items-center gap-2",
	"rounded-md px-2 text-base text-text-primary outline-none",
	"transition-colors duration-fast ease-out",
	"data-[selected=true]:bg-accent-wash data-[selected=true]:text-text-primary",
	"data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
	"[&>svg]:size-4 [&>svg]:shrink-0 [&>svg]:text-text-muted",
);

/** Trailing hint on a slash-menu row (shortcut, category). */
export const docSlashMenuHint = "ml-auto text-xs text-text-muted";

/** Empty state when the query matches nothing. */
export const docSlashMenuEmpty = "px-2 py-6 text-center text-sm text-text-muted";

/** Placeholder shown on an empty focused prose block ("type / for blocks"). */
export const docPlaceholder = cn(
	"pointer-events-none absolute select-none",
	"text-xl text-text-muted",
);
