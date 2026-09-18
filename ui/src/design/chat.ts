// Chat-sidebar class recipes.
//
// The agent rail is a *panel* surface, like apps and unlike pages: it is an
// operational object you check on and talk to, not a document you write prose
// into. So it borrows apps' density throughout - 36px chrome to line up with
// the shell strip and the apps bar, kit type tiers, 6px radii - and nothing
// here loosens toward the document measure.
//
// The one idea the surface is built around: three authors write into one
// column and must never read as one voice. A `user` message is a request; an
// `agent` message is the agent having *acted* to say something (its only way
// to speak is to append, so every line here was a deliberate write); a
// `system` message is the host reporting on the run itself. Three tiers,
// three treatments - accented card, plain prose, sunken note - because a
// reader who cannot tell them apart cannot tell what the agent chose to say
// from what the machinery said about it.
//
// Everything resolves to kit L2/L4 semantic names. No raw hex, nothing off the
// 4px grid.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/space-radius.md   §1 grid, §4 row heights
//   go/projects/nustackdev/design/palette.md        §2.2 text tiers, §2.6 status
//   go/projects/nustackdev/design/a11y.md           §4 aria, §5 focus ring

import { cn } from "@nustackdev/ui-kit";

/* =============================== the rail ================================ */

/**
 * The sidebar itself. A fixed measure, not a fraction: the conversation is the
 * secondary thing on screen and a surface that reflowed every time you opened
 * it would make the primary one unreadable.
 */
export const chatRoot = cn(
	"flex w-[360px] min-h-0 shrink-0 flex-col",
	"border-l border-border-subtle bg-bg-surface",
);

/** Collapsed: the strip that gives the rail back. Same 36px chrome. */
export const chatCollapsed = cn(
	"flex w-9 min-h-0 shrink-0 flex-col items-center gap-2 py-2",
	"border-l border-border-subtle bg-bg-surface",
);

/** The header bar. One line: a name, the run state, the actions. */
export const chatBar = cn(
	"flex h-9 shrink-0 items-center gap-2",
	"border-b border-border-subtle px-2",
);

export const chatBarTitle = "min-w-0 truncate text-sm font-medium text-text-primary";

/** The turn counter. Muted and monospaced: it is telemetry, not a control. */
export const chatTurns = "shrink-0 font-mono text-xs text-text-muted";

/* ============================= the transcript ============================ */

/** The scrolling body. Ordinary flow; chat.tsx pins it to the bottom. */
export const chatLog = "flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3";

/** Empty state, before anybody has asked anything. */
export const chatEmpty = cn(
	"flex min-h-0 flex-1 flex-col items-center justify-center gap-1",
	"p-6 text-center text-sm text-text-muted",
);

/** One message, whoever wrote it. The tier recipes below sit inside this. */
export const chatMessage = "flex flex-col gap-1";

/** Who is speaking. Small, muted, never the same weight as the words. */
export const chatAuthor = "text-xs font-medium uppercase tracking-wide text-text-muted";

/**
 * The human's ask. Accented and bordered, because it is the only thing on this
 * surface a person wrote, and everything below it is a consequence of it.
 */
export const chatAsk = cn(
	"whitespace-pre-wrap rounded-md px-2.5 py-2",
	"border border-accent-line bg-accent-wash",
	"text-sm leading-relaxed text-text-primary",
);

/** The agent talking. Plain prose, no box: it is the body text of the surface. */
export const chatReply = "whitespace-pre-wrap text-sm leading-relaxed text-text-primary";

/**
 * The host, about the run. Sunken and one tier back: it is machinery reporting
 * on itself, so it must not carry the weight of something the agent chose to
 * say. Capped and scrolling inside itself, because nothing guarantees it short.
 */
export const chatSystem = cn(
	"max-h-48 overflow-auto whitespace-pre-wrap",
	"rounded-md border border-border-subtle bg-bg-sunken p-2",
	"text-xs leading-relaxed text-text-secondary",
);

/** The loop itself failed. Danger tier, because nothing is coming after it. */
export const chatError = cn(
	"whitespace-pre-wrap rounded-md px-2.5 py-2",
	"border border-status-danger-line bg-status-danger-wash",
	"font-mono text-xs leading-relaxed text-status-danger-fg",
);

/** A turn is in flight. Sits at the foot of the log, under the last message. */
export const chatPending = "flex items-center gap-2 text-xs text-text-muted";

/* ============================== the composer ============================= */

/** The box you type in. Bordered off the log, never floating over it. */
export const chatComposer = cn("flex shrink-0 flex-col gap-2", "border-t border-border-subtle p-2");

/** The input. Auto-sizing is TS's job; this states the floor and the ceiling. */
export const chatInput = "max-h-40 min-h-[4.5rem] resize-none text-sm";

/** The row under the input: the hint on the left, the send button on the right. */
export const chatActions = "flex items-center justify-between gap-2";

/** The keyboard hint. One tier back, and it never competes with the button. */
export const chatHint = "flex items-center gap-1 text-xs text-text-muted";
