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
 * The plane's width: its grid at its widest, centred in the pane. The title
 * head and the column of cells both take it, so their rows line up track for
 * track.
 *
 * `wide` is the plane's full-width setting: no cap, so the content track
 * spans the pane while the gutters keep their width.
 */
function docPlaneWidth(wide: boolean): string {
	return cn("mx-auto w-full", wide ? "max-w-none" : "max-w-doc-plane");
}

/**
 * One row of a plane: the three tracks every row shares, left gutter,
 * content, right gutter (`--doc-grid`, tokens.css). The title, each cell,
 * a ghost, a draft and the drop line are each one of these, so the same
 * edges run through all of them without a row knowing about the others.
 */
export const docRow = "grid w-full grid-cols-(--doc-grid)";

/**
 * Where a row's parts go. Pinned to the first grid row as well as to their
 * column, so the order they render in never pushes one onto a second line.
 */
export const docGutterTrack = "col-[gutter-l] row-start-1";
export const docContentTrack = "col-[content] row-start-1 min-w-0";

/**
 * The column of cells. Each child is a `docRow`, and the ones that are not
 * (the tail, the slash menu) span it or float over it.
 *
 * The top pad is the air between the title and the first cell, 32. The
 * bottom one is the air under the last cell before the tail. Compact trims
 * both to 12.
 */
export function docColumn(wide = false, compact = false): string {
	return cn(
		"relative",
		docPlaneWidth(wide),
		compact ? "pt-3 pb-3" : "pt-8 pb-doc-pad-y",
		"flex flex-col gap-doc-cell-gap",
	);
}

/**
 * The scroll surface as the flex child a pane mounts it as.
 *
 * The 8px side pad is air between the gutters and the pane border, so a
 * cell's controls never sit on the divider of a split. The grid keeps
 * everything else inside: its gutters are tracks, not overhangs, so nothing
 * hangs past the pane's edge at any width.
 */
export const docPlaneSurface = cn(docPlane, "flex min-w-0 flex-1 flex-col px-2");

/**
 * Before a plane's value lands. Same quiet as the shell's boot state, 72 in
 * from the pane's edge (the surface's 8 plus 64), where it always sat.
 */
export const docPlaneLoading = "flex items-center gap-2 px-16 py-8 text-base text-text-muted";

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
 *
 * It sits in a `docRow`'s content track, where a cell's box sits.
 */
export const docGhost = (hinted: boolean) =>
	cn(
		docContentTrack,
		"w-full rounded-sm border-0 bg-transparent outline-none",
		"px-doc-cell-x py-doc-cell-y",
		"text-xl leading-relaxed text-text-primary",
		// An empty plane shows its hint at rest; otherwise only with the caret in.
		hinted
			? "placeholder:text-text-muted"
			: "placeholder:text-transparent focus:placeholder:text-text-muted",
	);

/**
 * A draft: what was typed into a ghost while its text cell is on the way.
 *
 * Plain text set where and how a text cell's first paragraph sits (cell pad,
 * field pad and the paragraph's own margin make the `py-5`), so the handoff
 * to the real editor moves nothing. Like a ghost, in a `docRow`'s content
 * track.
 */
export const docDraft = cn(
	docContentTrack,
	"w-full resize-none rounded-sm border-0 bg-transparent outline-none [field-sizing:content]",
	"px-doc-cell-x py-5",
	"font-display text-base leading-normal text-text-primary",
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
// cell's text starts at the content track's edge plus the cell's own 8px
// inset, so the trail and the title pay the same 8px -- `px-doc-cell-x` on
// both is alignment, not padding for its own sake.

/**
 * The band the trail and the title sit in. The same width as `docColumn`,
 * so its rows and the cells' rows share their tracks.
 *
 * The air between the title and the first cell is the column's top pad, not
 * anything here.
 */
export function docTitleHead(wide = false, compact = false): string {
	return cn(docPlaneWidth(wide), compact ? "pt-3" : "pt-4");
}

/**
 * The title's row: the plane's icon in the left gutter, the title in the
 * content track, so a long title wraps on the cells' text edge. It carries
 * the run-up the title always had: the full gap, or 28 in compact.
 */
export function docTitleRow(compact = false): string {
	return cn(docRow, compact ? "mt-7" : "mt-doc-title-gap");
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
 * `docTitleRow`, the row it shares with the plane's icon, rather than as
 * pad on the band, so the trail sits above it and the air lands between the
 * two. It fills that row's content track.
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
		docContentTrack,
		"block px-doc-cell-x py-0.5",
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
 * A cell's row: its gutter in the left track, its box (`docCell`) in the
 * content track. The row is the hover group, so standing anywhere on it,
 * the controls included, counts as being on the cell.
 *
 * The hovered row rides above its neighbours, so a gutter stack taller than
 * a short cell stays on top of the next row where it overhangs it, and wins
 * the pointer there (see `docGutter`). The caret's row rides one step lower.
 * A dragged cell fades whole, controls and all, while it travels.
 */
export function docCellRow(state: CellStateFlags = {}): string {
	return cn(
		docRow,
		"group/cell relative hover:z-20",
		state.focused && "z-10",
		state.dragging && "opacity-40",
	);
}

/**
 * One cell's box, in its row's content track. The content flows normally at
 * full measure; the gutter is its own track beside it, so nothing the gutter
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
		docContentTrack,
		"relative rounded-sm",
		"px-doc-cell-x",
		"py-doc-cell-y-program",
		"transition-colors duration-fast ease-out",
		// The grip is in the gutter, a sibling of this box, so its hover is
		// read off the row.
		!state.selected && "group-has-[[data-cell-grip]:hover]/cell:bg-doc-hover",
		state.selected && "bg-doc-selected",
		state.selectedStrong && "bg-doc-selected-strong",
		// The caret's cell gets no fill: it is already marked by the caret.
	);
}

/**
 * The gutter: the left track of a cell's row. It holds every affordance the
 * cell has: add and drag, copy the cell id, open the source. Hidden at rest
 * and revealed on hover or keyboard focus - a document at rest shows text,
 * not controls.
 *
 * The track is sized to hold the widest row of the stack - two `sm`
 * IconButtons side by side (24px each + a 2px gap) - and the rows
 * right-align into it, so their right edge is the content edge. The top pad
 * lines the first row up with the cell's output, which sits 8px in.
 *
 * The lane is as tall as the cell and no taller. The stack is 58px (8 of pad,
 * two 24px rows and a 2px gap), taller than a short cell, and if the lane
 * took its height a one-line cell would grow to fit its own controls. Size
 * containment keeps the stack out of the row's height, so it overhangs the
 * next row instead, and `hover:z-20` on the hovered row (`docCellRow`) lifts
 * it over that row so the overhang takes the pointer.
 *
 * The lane itself is a live hover target: it is part of the row, so
 * standing anywhere on it keeps the row's `group-hover/cell`. The 4px that
 * holds the controls off the text is padding INSIDE the stack, not on the
 * lane, so the stack's hit rect meets the content edge and the walk from the
 * text out to the controls never crosses a dead strip.
 */
export const docGutter = cn(
	docGutterTrack,
	"relative pt-2 [contain:size]",
	"flex flex-col items-end gap-0.5 select-none",
);

/**
 * Wrapper for the hover-only affordances inside the gutter. One reveal for all
 * three rows, so the cell's chrome arrives and leaves as a single object
 * rather than as six loose glyphs fading independently.
 *
 * Revealed and live are the same state, always. Hidden means `pointer-events:
 * none`, which is what keeps a neighbour's invisible stack from stealing the
 * pointer where it overhangs (see `docGutter`). Hover survives the walk off
 * the end of a short cell because `:hover` follows the DOM, not the box: the
 * stack is a descendant of the row, so standing on it keeps the row hovered
 * even where it is painted past the row's bottom. And the wrapper is one rect
 * covering both rows, so sliding between rows never crosses a dead strip even
 * where a row is narrower than the lane.
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
		// the cell is on screen, and the cell-high lane is its track.
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

/**
 * Drop indicator drawn between two cells during a drag. 2px accent line,
 * across the content track: it rides the top of the cell it would land
 * above, or a zero-height row after the last one.
 */
export const docDropIndicator = cn(
	"pointer-events-none absolute inset-x-0 h-doc-rail -translate-y-1/2",
	"rounded-full bg-doc-drop-line",
);

/**
 * The box a press off the cells drags out to select them. The selection's
 * own accent, translucent, over everything in the pane and in the way of
 * nothing. Placed in viewport coordinates by the plane.
 */
export const docBoxSelect = cn(
	"pointer-events-none fixed z-40 rounded-sm",
	"border border-doc-selected-line bg-doc-selected",
);

/* ============================== Cell interior =========================== */
//
// Every cell is a live program, so its interior is kit density even though the
// plane around it is not: the type inside it is chrome type, and the code box
// gets the same bordered-and-sunken treatment an editor in a tool gets. What makes it a document cell and not a
// panel is the outside - the gutter, the measure, the cell padding - and that
// is `docCellRow` and `docCell`'s job.
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
 * cell, not on it), in the cell's hue, running the lane's full height, which
 * is the cell's. It
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
