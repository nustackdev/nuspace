// Section status vocabulary.
//
// A nuspace block is a live program that can crash. The supervisor's
// observable surface IS a UI surface, so the state set here is the same one
// task-139 part 1 supervises, not a UI-side reinterpretation of it.
//
// Every state maps onto an existing palette status role via the --section-*
// aliases in ./tokens.css. No new hues. See that file for the reasoning on
// each mapping, in particular why `invalid` is warn and `failed` is danger.
//
// Three cues per state, so color is never load-bearing on its own (a11y.md §7):
//   - hue     the --section-* token
//   - shape   the dot silhouette (circle / square / triangle / diamond)
//   - label   the word itself
//
// Design refs:
//   palette.md      §2.6 status wash / line / fg
//   a11y.md         §7   color-blind safety
//   motion.md       §1   only `starting` and `running` animate

/** The six states a section can be in. Order is lifecycle order. */
export const SECTION_STATUSES = [
	"invalid",
	"idle",
	"starting",
	"running",
	"stopped",
	"failed",
] as const;

export type SectionStatus = (typeof SECTION_STATUSES)[number];

/**
 * Dot form. The non-color cue, rendered by `SectionStatusDot`.
 *
 * All six read cleanly at 8px, which is the constraint that picked them: an
 * X or a checkmark turns to mush at this size, a silhouette does not.
 */
export type SectionDotShape =
	| "hollow" // Outline circle          -> never ran
	| "pulse" // Filled circle, breathing -> coming up
	| "solid" // Filled circle            -> live
	| "square" // Filled square            -> ran, now over
	| "triangle" // Filled triangle          -> will not compile
	| "diamond"; // Filled diamond           -> ran and died

export interface SectionStatusToken {
	status: SectionStatus;
	/** Word shown in the pill. */
	label: string;
	/** One line for a tooltip. Says what happened, not what color it is. */
	hint: string;
	/** Kit StatusPill tone. Reuse the primitive, do not restyle it. */
	tone: "neutral" | "info" | "ok" | "warn" | "danger";
	shape: SectionDotShape;
	/** Tailwind utility names generated from tokens.css. */
	fg: string;
	wash: string;
	line: string;
	/** Transient states animate and are expected to leave on their own. */
	transient: boolean;
	/** States that carry a payload the block must render in place. */
	carries: "diagnostic" | "error" | null;
}

export const SECTION_STATUS: Record<SectionStatus, SectionStatusToken> = {
	invalid: {
		status: "invalid",
		label: "Invalid",
		hint: "Source does not compile",
		tone: "warn",
		shape: "triangle",
		fg: "text-section-invalid",
		wash: "bg-section-invalid-wash",
		line: "border-section-invalid-line",
		transient: false,
		carries: "diagnostic",
	},
	idle: {
		status: "idle",
		label: "Idle",
		hint: "Not started",
		tone: "neutral",
		shape: "hollow",
		fg: "text-section-idle",
		wash: "bg-section-idle-wash",
		line: "border-section-idle-line",
		transient: false,
		carries: null,
	},
	starting: {
		status: "starting",
		label: "Starting",
		hint: "Worker is coming up",
		tone: "info",
		shape: "pulse",
		fg: "text-section-starting",
		wash: "bg-section-starting-wash",
		line: "border-section-starting-line",
		transient: true,
		carries: null,
	},
	running: {
		status: "running",
		label: "Running",
		hint: "Live",
		tone: "ok",
		shape: "solid",
		fg: "text-section-running",
		wash: "bg-section-running-wash",
		line: "border-section-running-line",
		transient: false,
		carries: null,
	},
	stopped: {
		status: "stopped",
		label: "Stopped",
		hint: "Finished cleanly",
		tone: "neutral",
		shape: "square",
		fg: "text-section-stopped",
		wash: "bg-section-stopped-wash",
		line: "border-section-stopped-line",
		transient: false,
		carries: null,
	},
	failed: {
		status: "failed",
		label: "Failed",
		hint: "Ran and died",
		tone: "danger",
		shape: "diamond",
		fg: "text-section-failed",
		wash: "bg-section-failed-wash",
		line: "border-section-failed-line",
		transient: false,
		carries: "error",
	},
};

/**
 * Whether the block should paint a status rail down its gutter.
 *
 * Rest states stay silent - a page of idle blocks with six colored rails is
 * a christmas tree, not a document. The rail is for states the author has to
 * do something about, plus `running` so a live page reads as live.
 */
export function hasGutterRail(status: SectionStatus): boolean {
	return status === "invalid" || status === "failed" || status === "running";
}

/** Whether the block renders an inline payload panel under its content. */
export function hasPayload(status: SectionStatus): boolean {
	return SECTION_STATUS[status].carries !== null;
}
