// Apps-surface class recipes.
//
// Apps is a *panel* surface, not a document one. That is the whole reason it
// gets its own file rather than borrowing `document.ts`: a page is something
// you read and write prose into, so it has a reading measure, 16px type and a
// 64px column of air above the first block. An app is an operational object -
// a name, a state, a source file - so it uses kit density throughout: 28px
// rows, 32px chrome, 6px radii, editor-tier type. Nothing here loosens.
//
// What IS shared, deliberately:
//   - `design/tokens.css`         the doc-* interaction washes and the
//                                 --section-* status hues. An app and a
//                                 section have one status vocabulary because
//                                 they have one supervisor.
//   - `design/section-status.ts`  the six states, their tones and shapes.
//   - `design/rail.ts`            the rail geometry. The apps rail is flat,
//                                 so it uses RAIL.LANE / GAP / ROW and skips
//                                 INDENT, the guides and the twisty entirely.
//
// Everything resolves to kit L2/L4 semantic names or the doc-* / section-*
// names in ./tokens.css. No raw hex, nothing off the 4px grid.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §4 row heights, §1 grid
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers, §2.6 status
//   go/projects/nustackdev/design/motion.md         §3 nav rows
//   go/projects/nustackdev/design/a11y.md           §4 aria, §5 focus ring

import { cn } from "@nustackdev/ui-kit";

import { RAIL } from "./rail";

/* ============================== the rail ================================= */
//
// A flat list, so the three-lane geometry of the page rail collapses to two:
// a status lane and a truncating label, with the action lane still in flow.
// The status dot takes the lane the twisty takes on a page row, which is why
// the two rails line up when you flip between the surfaces.

export const appsAside = cn(
	"flex w-60 shrink-0 flex-col",
	"border-r border-border-subtle bg-bg-surface",
);

/** Header strip. Same 36px as the shell's top strip so the rules line up. */
export const appsHeader = cn(
	"flex h-9 shrink-0 items-center gap-1",
	"border-b border-border-subtle pl-3 pr-1.5",
);

export const appsHeaderLabel = cn(
	"flex-1 select-none text-xs font-medium uppercase tracking-[0.06em]",
	"text-text-muted",
);

export const appsScroll = "min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-1.5 py-1";

/**
 * The row shell. Same two-tier treatment as the page rail: hover is neutral
 * (`doc-hover`), selection is accent (`doc-selected`). The kit only ships
 * `accent-wash` and uses it for both, which makes a hovered row
 * indistinguishable from the open one.
 *
 * The row paints the wash, not the link inside it, so the wash spans the
 * status lane and the action lane too.
 */
export function appsRow(selected: boolean): string {
	return cn(
		"group/row relative flex items-center rounded-md",
		"h-7 pl-1.5 pr-1",
		"transition-colors duration-fast ease-out",
		// The row is the tree item, so the row carries the focus ring. Offset
		// 0: the kit's 2px offset gets clipped by the rail's own overflow.
		"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-0",
		selected ? "bg-doc-selected" : "hover:bg-doc-hover active:bg-doc-active",
	);
}

/** The status lane. Fixed width whether or not it holds a dot, so names align. */
export const appsLane = "flex shrink-0 items-center justify-center";

export const appsLaneStyle = { width: `${RAIL.LANE}px`, marginRight: `${RAIL.GAP}px` };

/**
 * The label, on top of a kit `NavLink`. NavLink stays because it is a real
 * anchor (cmd-click, middle-click, `aria-current="page"` for free). What it
 * does not own here is the background: the row shell paints that.
 */
export const appsLabel = cn(
	"h-full min-w-0 flex-1 gap-0 px-0",
	"bg-transparent hover:bg-transparent",
	"aria-[current=page]:bg-transparent data-[active=true]:bg-transparent",
	"focus-visible:ring-offset-0",
);

export const appsTitle = "min-w-0 flex-1 truncate";

/** Placeholder for an app with no name yet. One tier back, never italic. */
export const appsTitleEmpty = cn(appsTitle, "text-text-muted");

/**
 * The action lane. Always in flow and always the same width, so the name
 * truncates against a stable edge and nothing reflows on hover; only opacity
 * moves. Hidden controls are click-through too - an invisible button that
 * still eats a click is worse than no button.
 */
export const appsActions = cn(
	"flex shrink-0 items-center gap-0.5",
	"pointer-events-none opacity-0",
	"transition-opacity duration-fast ease-out",
	"group-hover/row:pointer-events-auto group-hover/row:opacity-100",
	"group-focus-within/row:pointer-events-auto group-focus-within/row:opacity-100",
	"[&:has([data-state=open])]:pointer-events-auto [&:has([data-state=open])]:opacity-100",
);

/** Shrink + re-tint for a row's action buttons, matching the page rail. */
export const appsAction = cn(
	"size-5 rounded-sm",
	"hover:bg-doc-active hover:text-text-primary",
	"focus-visible:ring-offset-0",
	"[&_svg]:size-3.5",
);

/** Rename happens in place, in the row, on a kit `Input` shrunk to it. */
export const appsInputBox = "flex min-w-0 flex-1 items-center";

export const appsInput = cn("h-6 min-w-0 flex-1 px-1 py-0 text-sm", "focus-visible:ring-offset-0");

export const appsSkeletonRow = "flex h-7 items-center px-1.5";

export const appsEmpty = "select-none px-2 py-3 text-sm text-text-muted";

/* ============================== the canvas =============================== */

/** Outer surface. `bg-bg-canvas`, same as the document, so the shell reads flat. */
export const appsCanvas = "flex min-h-0 min-w-0 flex-1 flex-col bg-bg-canvas";

/**
 * The app's header bar. One line: name, status, policy, actions.
 *
 * A masthead would be wrong here. `PageHeader` gives a document a banner, a
 * generated icon and a 4xl editable title, because a page is a thing you sit
 * inside and read. An app is a thing you check on, so its identity gets one
 * 36px strip and the rest of the surface goes to the source.
 */
export const appsBar = cn(
	"flex h-9 shrink-0 items-center gap-2",
	"border-b border-border-subtle bg-bg-surface px-3",
);

export const appsBarTitle = "min-w-0 truncate text-sm font-medium text-text-primary";

/** The policy chip. Muted on purpose: v1 has one policy and it is not a control. */
export const appsPolicy = cn(
	"shrink-0 rounded-sm px-1.5 py-0.5",
	"font-mono text-xs text-text-muted",
	"bg-bg-sunken",
);

/** Dirty marker: an unsaved buffer. A dot, not a word - it sits in chrome. */
export const appsDirtyDot = "size-1.5 shrink-0 rounded-full bg-status-warn";

/** The body under the bar. Scrolls as one; the editor sizes to its content. */
export const appsBody = "flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3";

/**
 * The editor box. Bordered and sunken, same treatment a program block's code
 * box gets, so a source editor looks like a source editor on both surfaces.
 * It takes the remaining height: an app is one file and there is nothing
 * below it to make room for.
 */
export const appsEditor = cn(
	"min-h-0 flex-1 overflow-hidden rounded-md",
	"border border-border-default bg-bg-sunken",
);

/** The payload panel: a diagnostic or a traceback, verbatim and monospaced. */
export const appsPayload = cn(
	"max-h-48 shrink-0 overflow-auto whitespace-pre-wrap",
	"rounded-md border p-2",
	"font-mono text-xs leading-relaxed",
);

/** Empty state, when no app is selected. Centered, one tier back. */
export const appsPlaceholder = cn(
	"flex min-h-0 flex-1 flex-col items-center justify-center gap-2",
	"p-8 text-center text-base text-text-muted",
);

/** The "no runner mounted" notice. Not an error: the space is simply not one. */
export const appsDetached = "shrink-0 px-3 pt-3";
