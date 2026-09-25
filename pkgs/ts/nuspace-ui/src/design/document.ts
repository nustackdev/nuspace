// Document-surface class recipes.
//
// The editor shell is written from zero (task-139 part 2), but its *styling*
// is not. These are the recipes every cell, gutter, handle and menu reaches
// for, so the shell never picks a token at the call site and we do not end up
// with forty one-off className strings that have to be unwound later.
//
// Everything below resolves to kit L2/L4 semantic names or the doc-* /
// cell-* names declared in ./tokens.css. No raw hex, no arbitrary values
// off the 4px grid.
//
// Density note. A document is not a panel. Horizontally it uses kit density
// (a cell's inner chrome is chrome: 32px rows, 6px radii). Vertically it is
// looser, but the air comes from the 16px/1.55 body line box, not from
// padding. See tokens.css for the full rule.

import { cn } from "@nustackdev/ui-kit";

import type { CellStatus } from "./cell-status";

/* ============================== Plane + column ============================ */

/**
 * Outer scroll surface. Canvas, not surface: the plane IS the background.
 * The scrollbar's lane is always reserved, so the column doesn't jump sideways
 * when the plane grows past the window and the bar appears.
 */
const docPlane = cn(
	"relative h-full w-full overflow-y-auto overflow-x-hidden [scrollbar-gutter:stable]",
	"bg-bg-canvas text-text-primary font-display",
);

/**
 * The reading column. Cells sit inside; the gutter hangs off the left edge
 * into the plane padding, which is why pad-x is doc-pad-x and not zero.
 *
 * `wide` is the plane's full-width setting: the column spans the pane instead
 * of stopping at the reading measure.
 */
export function docColumn(wide = false, compact = false): string {
	return cn(
		"relative mx-auto w-full",
		wide ? "max-w-none" : "max-w-doc",
		compact ? "px-doc-pad-x pt-3 pb-3" : "px-doc-pad-x pt-doc-pad-y pb-doc-pad-y",
		"flex flex-col gap-doc-cell-gap",
	);
}

/**
 * The scroll surface as the flex child a pane mounts it as.
 *
 * The side padding is the gutter's room. The gutter is `doc-gutter` wide and
 * hangs off the column into its `doc-pad-x`, which is narrower, so in a pane
 * too narrow to centre the column with air to spare the gutter used to hang
 * past the pane's left edge and get cut off. Padding the surface by the
 * difference (plus 8px of air off the pane border) means the gutter always
 * lands inside the pane. Symmetric, so a centred plane stays centred; on a
 * wide pane it changes nothing.
 */
export const docPlaneSurface = cn(
	docPlane,
	"flex min-w-0 flex-1 flex-col",
	"px-[calc(var(--spacing-doc-gutter)_-_var(--spacing-doc-pad-x)_+_0.5rem)]",
);

/** Before a plane's value lands. Same quiet as the shell's boot state. */
export const docPlaneLoading = "flex items-center gap-2 p-8 text-base text-text-muted";

/**
 * A ghost input: the line where a cell will be, before there is one.
 *
 * It says nothing at rest. A permanent control sitting at the foot of every
 * document repeating its own instructions is the loudest thing on a plane
 * whose job is to be quiet, and the affordance costs nothing to defer -- the
 * hint arrives the instant the caret does, which is the only moment it is an
 * answer to anything. Hence the transparent placeholder rather than a
 * conditional label: the text is always there for a screen reader, it is
 * merely not ink until you are in it.
 */
export const docGhost = cn(
	"w-full rounded-sm border-0 bg-transparent outline-none",
	"px-doc-cell-x py-doc-cell-y",
	"text-xl leading-relaxed text-text-primary",
	"placeholder:text-transparent focus:placeholder:text-text-muted",
);

/**
 * The run-off under the last cell, and the click target that opens it.
 *
 * Two jobs, one box. A document wants air past its end -- ending flush with
 * the window bottom reads as truncation -- and that air is also the only
 * large, obvious place to click to start writing, which is what every
 * document surface people already use does. `cursor-text` is the promise;
 * `docGhost` below the last cell is what the click lands in.
 */
export const docTail = "h-doc-tail w-full shrink-0 cursor-text";

/* ============================== Plane head ================================ */
//
// A plane opens with where it is and what it is called, and nothing else. No
// cover: a small trail at the top, then blank air, then the plane's icon when
// it has one (see ./icon.ts), then the name of the thing you are reading. What used to sit up here was chrome describing a
// document rather than the document, and it pushed the first line of actual
// writing off the fold.
//
// One left edge runs through all three of these and the cells below. A
// cell's text starts at the column's 24px side gutter plus the cell's own
// 8px inset, so the trail and the title pay the same 8px -- `px-doc-cell-x`
// on both is alignment, not padding for its own sake.

/**
 * The band the trail and the title sit in. Same measure and same side gutter
 * as `docColumn`, so the two columns are one column.
 *
 * The negative bottom margin eats half of the document column's own 64px top
 * pad. Without it the title and the first cell sit 64px apart on top of this
 * band's own trailing space, which reads as two documents rather than one.
 *
 * The `z-10` is load-bearing, not decoration: that same negative margin makes
 * the column's transparent top padding overlap the title, and the column is
 * later in the DOM, so without it the padding eats every click meant for the
 * heading.
 */
export function docTitleHead(wide = false, compact = false): string {
	return cn(
		"relative z-10 mx-auto w-full",
		wide ? "max-w-none" : "max-w-doc",
		// Compact: no run-up above the title and no overlap into the column,
		// whose own top pad shrinks with it (see `docColumn`).
		compact ? "px-doc-pad-x pt-3" : "px-doc-pad-x pt-4 -mb-8",
	);
}

/**
 * The trail, riding at the top of the band. It stays in the document rather
 * than moving up into the shell strip: the strip belongs to the window and
 * this says where one plane sits among the others, which is a fact about the
 * document.
 *
 * Small and quiet on purpose. It is the one thing up here you can click, and
 * the whole point of the air under it is that the title arrives on its own.
 */
export const docTrail = "px-doc-cell-x";

/**
 * The editable title. It is an `h1` with `contenteditable`, not an input and
 * not a button: the heading you read and the heading you type are the same
 * node, so there is no mode swap and no layout shift on click.
 *
 * The blank run-up above it (see `--spacing-doc-title-gap`) is carried by
 * `docTitleBlock`, the block it shares with the plane's icon, rather than as
 * pad on the band, so the trail sits above it and the air lands between the
 * two.
 *
 * No focus ring. A ring around a 40px heading is a box drawn around the plane's
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
export function docTitle(): string {
	return `${cn(
		"block w-full px-doc-cell-x py-0.5",
		"font-bold text-text-primary",
		"cursor-text whitespace-pre-wrap break-words outline-none",
		"empty:before:pointer-events-none empty:before:text-text-muted",
		"empty:before:content-[attr(data-placeholder)]",
	)} text-doc-title`;
}

/** Code inside a cell. Editor tier is 14px mono, per typography.md §1. */
export const docCode = "font-mono text-lg text-text-primary";

/* ============================== Cell ==================================== */

export interface CellStateFlags {
	/** The caret lives in this cell. No fill, gutter rail only. */
	focused?: boolean;
	/** Whole-cell selection (across an island boundary). Accent fill. */
	selected?: boolean;
	/** Part of a multi-cell selection. Stronger accent fill. */
	selectedStrong?: boolean;
	/** This cell is the one being dragged. Ghosted while it travels. */
	dragging?: boolean;
}

/**
 * One cell. The content flows normally at full measure; the gutter is hung
 * outside the cell's left edge (see `docGutter`), so nothing the gutter
 * renders can shift the reading column.
 *
 * Hover and pressed are NEUTRAL (doc-hover / doc-active); selection is the
 * accent tier. That split is deliberate - on a document, hovering every
 * paragraph in purple would make hover indistinguishable from selection.
 *
 * The cell does NOT tint on its own hover. Reading is the primary act on
 * this surface and the pointer crosses every cell on the way to anywhere,
 * so a fill that follows the cursor down the plane is noise against the one
 * thing the reader is trying to do. The tint is scoped to the drag handle
 * instead: it fires when the pointer is on the affordance that acts on the
 * whole cell, which is the only moment "this cell" is the unit you mean.
 * `:has()` rather than a React hover flag, because tracking pointer-enter
 * per cell would rerender the document on every mouse move.
 */
export function docCell(state: CellStateFlags = {}): string {
	return cn(
		"group/cell relative w-full rounded-sm",
		"px-doc-cell-x",
		"py-doc-cell-y-program",
		"transition-colors duration-fast ease-out",
		// The hovered cell rides above its neighbours, so a gutter stack that
		// overhangs a short cell stays on top of the next cell's lane.
		"hover:z-20",
		!state.selected && "has-[[data-cell-grip]:hover]:bg-doc-hover",
		state.selected && "bg-doc-selected",
		state.selectedStrong && "bg-doc-selected-strong",
		// The caret's cell gets no fill: it is already marked by the caret.
		// Its status rail is pinned instead, see `docStatusRail`.
		state.focused && "z-10",
		state.dragging && "opacity-40",
	);
}

/**
 * The gutter. Hangs off the cell's left edge into the plane padding and holds
 * every affordance the cell has: add and drag, copy the cell id, open the
 * source. Hidden at rest and revealed on cell hover or keyboard focus - a
 * document at rest shows text, not controls.
 *
 * Sized to hold the widest row - two `sm` IconButtons side by side (24px each
 * + a 2px gap) - which is what makes the gutter one lane instead of two
 * overlapping ones. The top offset lines the first row up with the cell's
 * output, which sits 8px in.
 *
 * The lane itself is inert. Three stacked rows are 76px tall (3x24 + 2x2),
 * taller than a one-line cell, so a cell's gutter hangs past the bottom of
 * the cell it belongs to and straight across the next cell's gutter slot. If
 * both were live hit targets the lower one would win by document order and
 * moving down your own controls would hand you the neighbour's - which is
 * exactly what it did. `pointer-events-none` here and on the hidden stack
 * means only the revealed stack takes the pointer, so at most one cell's
 * controls are live at a time and the overhang unambiguously belongs to the
 * cell that is showing. See `docGutterAffordances`.
 *
 * The 4px that holds the controls off the text is padding INSIDE the stack,
 * not padding on the lane. On the lane it was a dead strip: the stack's hit
 * rect stopped 4px short of the cell's left edge, and that strip is inert,
 * so walking from the text out to the controls dropped the cell's `:hover`
 * before the stack was reached and the stack went inert with it. The pointer
 * is only hit-tested where it is sampled, so a fast enough swipe jumped the
 * strip and worked while a slow one did not. The two rects touch now, and
 * the walk is continuous at any speed.
 */
//
// The lane is a live hover target now, spanning the cell's full height (and
// at least the stack's height, min-h-14). It is a descendant of the cell, so
// standing anywhere in the column keeps the cell's `group-hover/cell`, and
// the controls stay pinned at the top via pt-2. The overhang problem above is
// handled by `hover:z-20` on the cell: the hovered cell paints over the next
// one, so its overhanging lane and stack win the hit test.
export const docGutter = cn(
	"absolute right-full top-0 bottom-0 min-h-14 w-doc-gutter pt-2",
	"flex flex-col items-end gap-0.5 select-none",
);

/**
 * Wrapper for the hover-only affordances inside the gutter. One reveal for all
 * three rows, so the cell's chrome arrives and leaves as a single object
 * rather than as six loose glyphs fading independently.
 *
 * Revealed and live are the same state, always. Hidden means `pointer-events:
 * none`, which is what keeps a neighbour's invisible stack from stealing the
 * pointer (see `docGutter`). Hover survives the walk out into the lane because
 * `:hover` follows the DOM, not the box: the stack is a descendant of the
 * cell, so standing on it keeps the cell hovered even though it is painted
 * outside the cell's rect. And the wrapper is one rect covering all three
 * rows, so sliding between rows never crosses a dead strip even where a row is
 * narrower than the lane.
 *
 * Reveal rules, in order of how they burn:
 *  - Hover, the ordinary one.
 *  - Focus-within scoped to the STACK, not to the cell. Cell-scoped
 *    focus-within pinned the controls open for as long as the caret sat in the
 *    cell, which is most of the time you are writing; a keyboard user who has
 *    tabbed onto one of these buttons still keeps them.
 *  - An open menu or popover. Tooltips cannot pin it: Radix reports them as
 *    `delayed-open`/`instant-open` and portals the content out of this
 *    subtree, so neither half of the selector can see one.
 */
export function docGutterAffordances(pinned = false): string {
	return cn(
		// Sticky: in a tall cell the stack rides the top of the viewport while
		// the cell is on screen, and the full-height lane is its track.
		"sticky top-2 flex flex-col items-end gap-0.5 pr-1",
		"transition-opacity duration-fast ease-out",
		pinned
			? "pointer-events-auto opacity-100"
			: cn(
					"pointer-events-none opacity-0",
					"group-hover/cell:pointer-events-auto group-hover/cell:opacity-100",
					// Keyboard focus only: a mouse click leaves focus on the button and must
					// not pin the stack open after the pointer leaves.
					"has-[:focus-visible]:pointer-events-auto has-[:focus-visible]:opacity-100",
					"[&:has([data-state=open])]:pointer-events-auto [&:has([data-state=open])]:opacity-100",
				),
	);
}

/** One row of the gutter stack. Right-aligned, so the lane has a clean edge. */
export const docGutterRow = "flex items-center justify-end gap-0.5";

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

/** Drop indicator drawn between two cells during a drag. 2px accent line. */
export const docDropIndicator = cn(
	"pointer-events-none absolute inset-x-0 h-doc-rail -translate-y-1/2",
	"rounded-full bg-doc-drop-line",
);

/* ============================== Cell interior =========================== */
//
// Every cell is a live program, so its interior is kit density even though the
// plane around it is not: the type inside it is chrome type, and the code box
// gets the same bordered-and-sunken treatment an editor in a tool gets. What makes it a document cell and not a
// panel is the outside - the gutter, the measure, the cell padding - and that
// is `docCell`'s job.
//
// The cell has no control row of its own. Status, the id and the code toggle
// all live in the gutter now, on the same three rows every cell gets, so what
// is left inside the cell is only what the program produced.

/** The cell's own stack: alert, editor, fields. All output, no chrome. */
export const docProgram = "flex flex-col gap-1";

/**
 * "unsaved" plus its two Kbd caps, parked under the open source editor.
 *
 * Quiet and right-aligned: it is a reminder about the buffer you are looking
 * at, and it says nothing once that buffer is closed.
 */
export const docSourceDirty = "flex items-center gap-1 self-end text-xs text-text-muted";

/** The cell's mounted ui refs. Looser gap: these are whole widgets. */
export const docProgramFields = "flex flex-col gap-3 py-1";

/** The "runs headless" line, when a cell mounts nothing. */
export const docProgramHeadless = "py-1 text-base text-text-muted";

/**
 * The code box around Monaco. Bordered and sunken, so a source editor looks
 * like a source editor wherever it turns up. It sizes to its content rather
 * than filling: a cell is one of many on the Plane and there is something
 * below it to make room for.
 */
export const docCodeBox = cn(
	"w-full overflow-hidden rounded-md",
	"border border-border-default bg-bg-sunken",
);

/* ============================== Status ================================== */

/**
 * The status rail: a 2px line down the gutter lane's inner edge (beside the
 * cell, not on it), in the cell's hue, running the lane's full height. It
 * is the cell's one state indicator, so every state paints one, idle
 * included (muted gray). Same visibility as the gutter controls: cell hover,
 * or pinned while the source is open or the cell is selected.
 */
export function docStatusRail(status: CellStatus, pinned = false): string {
	return cn(
		"absolute right-0 top-0 bottom-0 w-doc-rail rounded-full",
		"transition-[color,background-color,opacity] duration-fast ease-out",
		pinned ? "opacity-100" : "opacity-0 group-hover/cell:opacity-100",
		{
			invalid: "bg-cell-invalid",
			idle: "bg-cell-idle",
			starting: "bg-cell-starting",
			running: "bg-cell-running",
			stopped: "bg-cell-stopped",
			failed: "bg-cell-failed",
		}[status],
	);
}

/**
 * The traceback / diagnostic body inside a cell's status panel. The panel
 * itself is the kit's `Alert` (it already owns the wash, the line, the tone
 * icon and `role="alert"`); all that is left for the document layer is the
 * fact that a python traceback is preformatted text and has to be able to
 * scroll sideways without widening the reading column.
 */
export const docStatusTrace = cn(
	"font-mono text-sm whitespace-pre-wrap break-words",
	"max-h-64 overflow-auto",
);

/* ============================== Slash menu =============================== */

/**
 * Slash menu surface. Same surface grammar as a kit DropdownMenu (elevated,
 * default border, lg radius) so it does not read as a foreign widget on a
 * plane that also hosts kit primitives.
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
