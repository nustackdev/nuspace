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
// looser, but the air comes from the 16px/1.55 body line box, not from
// padding. See tokens.css for the full rule.

import { cn } from "@nustackdev/ui-kit";

import type { SectionStatus } from "./section-status";
import { hasGutterRail } from "./section-status";

/* ============================== page + column ============================ */

/** Outer scroll surface. Canvas, not surface: the page IS the background. */
const docPage = cn(
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

/** The scroll surface as the flex child the Viewer mounts it as. */
export const docPageSurface = cn(docPage, "flex min-w-0 flex-1 flex-col");

/** Before a page's value lands. Same quiet as the shell's boot state. */
export const docPageLoading = "flex items-center gap-2 p-8 text-base text-text-muted";

/**
 * A ghost input: the line where a block will be, before there is one.
 *
 * It says nothing at rest. A permanent control sitting at the foot of every
 * document repeating its own instructions is the loudest thing on a page
 * whose job is to be quiet, and the affordance costs nothing to defer -- the
 * hint arrives the instant the caret does, which is the only moment it is an
 * answer to anything. Hence the transparent placeholder rather than a
 * conditional label: the text is always there for a screen reader, it is
 * merely not ink until you are in it.
 */
export const docGhost = cn(
	"w-full rounded-sm border-0 bg-transparent outline-none",
	"px-doc-block-x py-doc-block-y",
	"text-xl leading-relaxed text-text-primary",
	"placeholder:text-transparent focus:placeholder:text-text-muted",
);

/**
 * The run-off under the last block, and the click target that opens it.
 *
 * Two jobs, one box. A document wants air past its end -- ending flush with
 * the window bottom reads as truncation -- and that air is also the only
 * large, obvious place to click to start writing, which is what every
 * document surface people already use does. `cursor-text` is the promise;
 * `docGhost` below the last block is what the click lands in.
 */
export const docTail = "h-doc-tail w-full shrink-0 cursor-text";

/* ============================== page head ================================ */
//
// A page opens with where it is and what it is called, and nothing else. No
// cover, no icon: a small trail at the top, then blank air, then the name of
// the thing you are reading. What used to sit up here was chrome describing a
// document rather than the document, and it pushed the first line of actual
// writing off the fold.
//
// One left edge runs through all three of these and the blocks below. A
// block's text starts at the column's 24px side gutter plus the block's own
// 8px inset, so the trail and the title pay the same 8px -- `px-doc-block-x`
// on both is alignment, not padding for its own sake.

/**
 * The band the trail and the title sit in. Same measure and same side gutter
 * as `docColumn`, so the two columns are one column.
 *
 * The negative bottom margin eats half of the document column's own 64px top
 * pad. Without it the title and the first block sit 64px apart on top of this
 * band's own trailing space, which reads as two documents rather than one.
 *
 * The `z-10` is load-bearing, not decoration: that same negative margin makes
 * the column's transparent top padding overlap the title, and the column is
 * later in the DOM, so without it the padding eats every click meant for the
 * heading.
 */
export const docTitleHead = cn("relative z-10 mx-auto w-full max-w-doc", "px-doc-pad-x pt-4 -mb-8");

/**
 * The trail, riding at the top of the band. It stays in the document rather
 * than moving up into the shell strip: the strip belongs to the window and
 * this says where one page sits among the others, which is a fact about the
 * document.
 *
 * Small and quiet on purpose. It is the one thing up here you can click, and
 * the whole point of the air under it is that the title arrives on its own.
 */
export const docTrail = "px-doc-block-x";

/**
 * The editable title. It is an `h1` with `contenteditable`, not an input and
 * not a button: the heading you read and the heading you type are the same
 * node, so there is no mode swap and no layout shift on click.
 *
 * The top margin is the blank run-up (see `--spacing-doc-title-gap`), carried
 * here rather than as pad on the band so the trail sits above it and the air
 * lands between the two.
 *
 * No focus ring. A ring around a 40px heading is a box drawn around the page's
 * name, and the caret already says where you are. The placeholder is a `::before` on the empty element
 * rather than a second absolutely positioned node, so it can never fall out of
 * alignment with that caret.
 */
// `text-doc-title` is concatenated rather than merged, and it has to be.
// `cn` is tailwind-merge, which resolves conflicts from a table of the classes
// it ships knowing about. Our size is not in that table, so it is read as a
// `text-*` COLOUR, `text-text-primary` in the same call is taken to conflict
// with it, and last-one-wins drops the size on the floor. The rule compiles,
// the class reaches the bundle, and the title still renders at body size.
// Nothing else in here conflicts, so appending it afterwards is safe. Any
// future custom type token meeting a text colour has the same problem.
export const docTitle = `${cn(
	"mt-doc-title-gap block w-full px-doc-block-x py-0.5",
	"font-bold text-text-primary",
	"cursor-text whitespace-pre-wrap break-words outline-none",
	"empty:before:pointer-events-none empty:before:text-text-muted",
	"empty:before:content-[attr(data-placeholder)]",
)} text-doc-title`;

/** Code inside a block. Editor tier is 14px mono, per typography.md §1. */
export const docCode = "font-mono text-lg text-text-primary";

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
		"py-doc-block-y-program",
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
 * every affordance the block has: add and drag, copy the section id, open the
 * source. Hidden at rest and revealed on block hover or keyboard focus - a
 * document at rest shows text, not controls.
 *
 * Sized to hold the widest row - two `sm` IconButtons side by side (24px each
 * + a 2px gap) - which is what makes the gutter one lane instead of two
 * overlapping ones. The top offset lines the first row up with the block's
 * output, which sits 8px in.
 *
 * The lane itself is inert. Three stacked rows are 76px tall (3x24 + 2x2),
 * taller than a one-line block, so a block's gutter hangs past the bottom of
 * the block it belongs to and straight across the next block's gutter slot. If
 * both were live hit targets the lower one would win by document order and
 * moving down your own controls would hand you the neighbour's - which is
 * exactly what it did. `pointer-events-none` here and on the hidden stack
 * means only the revealed stack takes the pointer, so at most one block's
 * controls are live at a time and the overhang unambiguously belongs to the
 * block that is showing. See `docGutterAffordances`.
 *
 * The 4px that holds the controls off the text is padding INSIDE the stack,
 * not padding on the lane. On the lane it was a dead strip: the stack's hit
 * rect stopped 4px short of the block's left edge, and that strip is inert,
 * so walking from the text out to the controls dropped the block's `:hover`
 * before the stack was reached and the stack went inert with it. The pointer
 * is only hit-tested where it is sampled, so a fast enough swipe jumped the
 * strip and worked while a slow one did not. The two rects touch now, and
 * the walk is continuous at any speed.
 */
export const docGutter = cn(
	"pointer-events-none absolute right-full w-doc-gutter top-2",
	"flex flex-col items-end gap-0.5 select-none",
);

/**
 * Wrapper for the hover-only affordances inside the gutter. One reveal for all
 * three rows, so the block's chrome arrives and leaves as a single object
 * rather than as six loose glyphs fading independently.
 *
 * Revealed and live are the same state, always. Hidden means `pointer-events:
 * none`, which is what keeps a neighbour's invisible stack from stealing the
 * pointer (see `docGutter`). Hover survives the walk out into the lane because
 * `:hover` follows the DOM, not the box: the stack is a descendant of the
 * block, so standing on it keeps the block hovered even though it is painted
 * outside the block's rect. And the wrapper is one rect covering all three
 * rows, so sliding between rows never crosses a dead strip even where a row is
 * narrower than the lane.
 *
 * Reveal rules, in order of how they burn:
 *  - hover, the ordinary one.
 *  - focus-within scoped to the STACK, not to the block. Block-scoped
 *    focus-within pinned the controls open for as long as the caret sat in the
 *    block, which is most of the time you are writing; a keyboard user who has
 *    tabbed onto one of these buttons still keeps them.
 *  - an open menu or popover. Tooltips cannot pin it: Radix reports them as
 *    `delayed-open`/`instant-open` and portals the content out of this
 *    subtree, so neither half of the selector can see one.
 */
export const docGutterAffordances = cn(
	"pointer-events-none flex flex-col items-end gap-0.5 pr-1",
	"opacity-0 transition-opacity duration-fast ease-out",
	"group-hover/block:pointer-events-auto group-hover/block:opacity-100",
	"focus-within:pointer-events-auto focus-within:opacity-100",
	"[&:has([data-state=open])]:pointer-events-auto [&:has([data-state=open])]:opacity-100",
);

/** One row of the gutter stack. Right-aligned, so the lane has a clean edge. */
export const docGutterRow = "flex items-center justify-end gap-0.5";

/**
 * The status slot, third row of the gutter stack.
 *
 * A 24px box holding an 8px dot -- the same box a kit `IconButton sm` is. The
 * dot alone would be a loose 8px glyph in a column of 24px squares, sitting
 * the row off the rhythm the other two keep.
 *
 * Deliberately not a control yet: a span, so nothing here takes focus or the
 * pointer, and the dot is a readout rather than something that looks clickable
 * and is not. What this buys is that the slot is already the right size and
 * in the right place, so the day the dot becomes a play/stop button it swaps
 * in and no geometry moves.
 */
export const docGutterStatus = "inline-flex size-6 items-center justify-center";

/**
 * The code toggle, on top of a kit `Toggle sm`. Trims the horizontal padding
 * so its box is the 24px square an `IconButton sm` is: the gutter is a column
 * of one-glyph controls and a 26px one in the stack reads as a wobble.
 */
export const docGutterToggle = "px-1";

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

/* ============================== block interior =========================== */
//
// Every block is a live section, so its interior is kit density even though the page around it is not: the type
// inside it is chrome type, and the code box gets the same bordered-and-sunken
// treatment an app's editor gets. What makes it a document block and not a
// panel is the outside - the gutter, the measure, the block padding - and that
// is `docBlock`'s job.
//
// The block has no control row of its own. Status, the id and the code toggle
// all live in the gutter now, on the same three rows every block gets, so what
// is left inside the block is only what the program produced.

/** The block's own stack: alert, editor, fields. All output, no chrome. */
export const docProgram = "flex flex-col gap-1";

/**
 * "unsaved" plus its two Kbd caps, parked under the open source editor.
 *
 * Quiet and right-aligned: it is a reminder about the buffer you are looking
 * at, and it says nothing once that buffer is closed.
 */
export const docSourceDirty = "flex items-center gap-1 self-end text-xs text-text-muted";

/** The block's mounted ui refs. Looser gap: these are whole widgets. */
export const docProgramFields = "flex flex-col gap-3 py-1";

/** The "runs headless" line, when a block mounts nothing. */
export const docProgramHeadless = "py-1 text-base text-text-muted";

/**
 * The code box around Monaco. Bordered and sunken, so a source editor looks
 * like a source editor wherever it turns up. It sizes to its content rather
 * than filling: a block is one of many on the Plane and there is something
 * below it to make room for.
 */
export const docCodeBox = cn(
	"w-full overflow-hidden rounded-md",
	"border border-border-default bg-bg-sunken",
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

/** The row's label. Owns the line: it truncates, the hint never does. */
export const docSlashMenuItemLabel = "flex-1 truncate text-left";

/** Trailing hint on a slash-menu row (shortcut, category). Mono: it is a key. */
export const docSlashMenuHint = "ml-auto font-mono text-xs text-text-muted";

/** Empty state when the query matches nothing. */
export const docSlashMenuEmpty = "px-2 py-6 text-center text-sm text-text-muted";
