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
// looser, but the air comes from the 14px/1.45 prose line box, not from
// padding: a cell is a near-plain box. See tokens.css for the full rule.

import { cn, commandSurfaceClasses } from "@nustackdev/ui-kit";

import { CELL_STATUS, type CellStatus } from "./cell-status";

/* ============================== Plane + column ============================ */

/**
 * Outer scroll surface, on the page: the plane IS the background.
 * The scrollbar's lane is always reserved, so the column doesn't jump sideways
 * when the plane grows past the window and the bar appears.
 */
const docPlane = cn(
	"relative h-full w-full overflow-y-auto overflow-x-hidden [scrollbar-gutter:stable]",
	"bg-nuspace-page text-text-primary font-display",
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
 * A pane with no plane to draw: there is none by that id, or it runs without
 * a view. The kit's `EmptyState` in the document grid's content track,
 * centred in the pane's height, with its one way out under it.
 */
export const docPlaneAbsent = cn(docRow, docPlaneWidth(false), "flex-1 content-center");

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
 * It sits in a `docRow`'s content track, where a cell's box sits, and its
 * line is a text cell's first line: same inset, same type.
 */
export const docGhost = (hinted: boolean) =>
	cn(
		docContentTrack,
		"w-full rounded-sm border-0 bg-transparent outline-none",
		"px-doc-cell py-doc-line",
		"text-lg text-text-primary",
		// An empty plane shows its hint at rest; otherwise only with the caret in.
		hinted
			? "placeholder:text-text-muted"
			: "placeholder:text-transparent focus:placeholder:text-text-muted",
	);

/**
 * A draft: what was typed into a ghost while its text cell is on the way.
 *
 * Plain text set where and how a text cell's first paragraph sits (the
 * cell's pad plus the prose box's, see `--spacing-doc-line`; the first
 * paragraph has no margin of its own there), so the handoff to the real
 * editor moves nothing. Like a ghost, in a `docRow`'s content track.
 */
export const docDraft = cn(
	docContentTrack,
	"w-full resize-none rounded-sm border-0 bg-transparent outline-none [field-sizing:content]",
	"px-doc-cell py-doc-line",
	"font-display text-lg text-text-primary",
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
// cell's text starts at the content track's edge plus the cell's own pad,
// so the trail and the title pay the same pad -- `px-doc-cell` on both is
// alignment, not padding for its own sake.

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
export const docTrail = "px-doc-cell";

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
		"block px-doc-cell py-0.5",
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
	/** The caret lives in this cell. No fill: the caret marks it. */
	focused?: boolean;
	/** Whole-cell selection (across an island boundary). Accent fill. */
	selected?: boolean;
	/** Part of a multi-cell selection. Stronger accent fill. */
	selectedStrong?: boolean;
	/** This cell is the one being dragged. Ghosted while it travels. */
	dragging?: boolean;
}

/**
 * A cell's row: its controls in the two gutters (`docGutterLane`), its box
 * (`docCell`) in the content track between them. Never shorter than a row of
 * controls (`--spacing-doc-row`), so a row's controls always fit inside it
 * and never reach into the next one. A dragged cell fades whole, controls and
 * all, while it travels.
 *
 * `data-selected` marks the one selected cell, which shows its controls.
 */
export function docCellRow(state: CellStateFlags = {}): string {
	return cn(docRow, "group/cell relative min-h-doc-row", state.dragging && "opacity-40");
}

/**
 * One cell's box, in its row's content track. The content flows normally at
 * full measure; the gutter is its own track beside it, so nothing the gutter
 * renders can shift the reading column.
 *
 * Near-plain: the same small pad on every side for every cell, whatever it
 * mounts. What it holds brings its own air (prose pads its own box, a widget
 * has its chrome), so the cell adds only enough that its content never
 * touches the wash edge or the next cell.
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
		"p-doc-cell",
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
 * One gutter of a cell's row, left or right, holding one row of controls.
 * A document at rest shows text, not controls, so they show only when this
 * row is the one in question: hovered, one of its controls reached by
 * keyboard, it is the one selected cell, or its menu is open. `data-pinned`
 * on the lane keeps it out regardless (the source toggle of a broken cell, or
 * of one whose source is open). All of it is read off the row in CSS, so no
 * row knows about any other and the plane does not arbitrate.
 *
 * The top pad (`--spacing-doc-gutter-top`) centres the 24px controls on a
 * text cell's first line. Each sits against the content edge, 4px off it.
 */
export function docGutterLane(side: "left" | "right"): string {
	return cn(
		side === "left" ? "col-[gutter-l] justify-end pr-1" : "col-[gutter-r] justify-start pl-1",
		"row-start-1 flex items-start pt-doc-gutter-top select-none",
		"opacity-0 transition-opacity duration-fast ease-out",
		"group-hover/cell:opacity-100",
		"group-has-[[data-cell-gutter]_:focus-visible]/cell:opacity-100",
		"group-data-[selected]/cell:opacity-100",
		"group-has-[[data-cell-grip][data-state=open]]/cell:opacity-100",
		"data-[pinned]:opacity-100",
	);
}

/**
 * The controls in a lane, side by side. Sticky: in a tall cell they ride the
 * top of the viewport while the cell is on screen, the lane as their track.
 */
export const docGutterControls = "sticky top-2 flex items-center gap-0.5";

/**
 * The code toggle, on top of a kit `Toggle sm`. Trims the horizontal padding
 * so its box is the 24px square an `IconButton sm` is, like every other
 * control in the gutters.
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
 * "unsaved" plus its kit `Shortcut` (mod enter), parked under the open source editor.
 *
 * Quiet and right-aligned: it is a reminder about the buffer you are looking
 * at, and it says nothing once that buffer is closed.
 */
export const docSourceDirty = "flex items-center gap-1 self-end text-xs text-text-muted";

/**
 * The cell's mounted ui refs. The gap is what two cells put between their
 * contents (a pad, the gap between cells, a pad: 4 + 4 + 4), so two text
 * blocks sit the same distance apart whether they share a cell or not.
 */
export const docProgramFields = "flex flex-col gap-3";

/**
 * The line a cell that mounts nothing keeps, one line high: a kit `Badge
 * dashed`, set in mono like the lens's empty value (ui-kit's lens columns).
 * `leading-none` again because the badge's own is merged away by its size.
 */
export const docProgramHeadless = "flex py-1";
export const docProgramHeadlessChip = "select-none font-mono font-normal leading-none";

/**
 * A cell whose view is on the way: two kit `Skeleton` text lines, the second
 * shorter, like the rail's. Small, so a waiting cell never pushes the page.
 */
export const docProgramLoading = "flex flex-col gap-1.5 py-1";
export const docProgramLoadingLine = "w-2/3";
export const docProgramLoadingLineShort = "w-1/3";

/* ============================== Viewer skeleton =========================== */

// What a pane shows while its plane is on the way, at boot and on a switch
// alike: the title row and a few cells, as kit `Skeleton` bars on the same
// grid the real plane uses, so nothing moves sideways when it lands.

/** The whole placeholder, filling the pane's scroll surface. */
export const docSkeleton = "flex min-w-0 flex-1 flex-col";

/** The bar where the title goes, in the title row's content track. */
export const docSkeletonTitle = cn(docContentTrack, "h-9 w-1/2 self-center");

/** One cell's worth: text lines in the content track, at the cell's pad. */
export const docSkeletonCell = cn(docContentTrack, "flex flex-col gap-2 p-doc-cell");

/* ============================== Status ================================== */

/**
 * The cell's status, on the source toggle's glyph: the code icon takes the
 * cell's hue. It is the cell's one state indicator, so every state paints
 * one, idle included (muted gray). The glyph carries its own colour class,
 * which beats the colour the kit `Toggle` sets on itself, so the hue holds
 * on hover and while pressed. Colour is never the only cue: the toggle's
 * label and tooltip name the state. It shows when its gutter does, and stays
 * out on a broken cell (`docGutterLane`).
 */
export function docGutterStatus(status: CellStatus): string {
	return CELL_STATUS[status].fg;
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
 * The slash menu: a command box, not a dropdown. A kit popover wearing the
 * command palette's surface, rows and headings, since focus stays in the
 * ghost and the palette would take it. Its height is the room it opened
 * into, up to a cap.
 */
export const docSlashMenu = cn(
	commandSurfaceClasses,
	"flex w-[26rem] max-w-[calc(100vw-2rem)] flex-col p-0",
	"max-h-[min(27.5rem,var(--radix-popover-content-available-height))]",
);

/** The scrolling rows, between the edge and the footer. */
export const docSlashList = "min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-1.5";
