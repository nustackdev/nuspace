// Apps-canvas class recipes.
//
// Apps is a *panel* surface, not a document one. That is the whole reason it
// gets its own file rather than borrowing `document.ts`: a page is something
// you read and write prose into, so it has a reading measure, 16px type and a
// 64px column of air above the first block. An app is an operational object -
// a name, a state, a source file - so it uses kit density throughout: 28px
// rows, 32px chrome, 6px radii, editor-tier type. Nothing here loosens.
//
// Only the canvas lives here. The apps rail is the same object as the pages
// rail at depth zero, so it takes its recipes from `./rail.ts` whole.
//
// What IS shared, deliberately:
//   - `design/tokens.css`         the doc-* interaction washes and the
//                                 --section-* status hues. An app and a
//                                 section have one status vocabulary because
//                                 they have one supervisor.
//   - `design/section-status.ts`  the six states, their tones and shapes.
//   - `design/rail.ts`            the whole rail. The apps rail is flat, so it
//                                 uses RAIL.LANE / GAP / ROW and skips INDENT,
//                                 the guides and the twisty entirely.
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
