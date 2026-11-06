// What the person tried to do, and who decides what it means.
//
// Lower layers report intents, upper layers decide. A cell's markdown editor
// (the kit's markdown handle) reports a `MarkdownIntent`: the caret tried to leave
// it, Backspace on blank, `/` into a blank one, Cmd+Enter. The input line
// reports an `InputIntent`: text typed with the menu closed, or Enter. The
// title above the plane reports a `TitleIntent`: Enter, or leaving it down
// or right at its end. Nothing reports more than that, and nothing above
// reads a lower layer's internals to find out.
//
// Routing is the same for all three:
//
//   editor intent   -> the sets bound to one of the cell's classes
//   input / title   -> the sets whose class has a default spec installed
//   each in list order until one answers true; none does: the core default
//
// The core defaults are what the plane does with no sugar at all:
//
//   leave, not extending   today's step: the neighbour's open source takes
//                          the caret, else the neighbour is selected
//   anything else, editor  nothing, the editor goes on as if no host existed
//   input text             the menu opens, the text its query (the line's)
//   input Enter            nothing
//   title Enter at end,    into the cells: the top cell's open source, else
//   title leave            it is selected; the end line on an empty plane
//   title Enter mid-text   nothing, the title blurs
//
// A read-only plane routes nothing: no sugar, and the editor keeps every key.
//
// Hints are bound the same way. The input line shows the placeholder of the
// first set it would offer an intent to; a cell's markdown editor draws the hints
// of the first set bound to one of its classes, while the caret is in it
// (./focus/useCaret.ts). With none, the line says "Press / for cells" and
// an editor draws only its own placeholder.

import type { MarkdownIntent } from "@nustackdev/ui-kit";
import type { PlaneApi } from "./api";
import type { Sugar } from "./sugar";
import type { CellSpec, ExitDir } from "./types";

export type { MarkdownIntent };

/** On the input line, menu closed: text typed into it, or Enter. */
export type InputIntent = { kind: "text"; text: string } | { kind: "enter" };

/** In the title: Enter (`end`: the caret at the end), or leaving it at its end. */
export type TitleIntent =
	| { kind: "enter"; end: boolean }
	| { kind: "leave"; dir: "down" | "right" };

/** The installed spec that is `cls`'s default, null when none is. */
export function defaultSpecOf(cellSpecs: readonly CellSpec[], cls: string): string | null {
	return cellSpecs.find((s) => s.default_for?.includes(cls))?.name ?? null;
}

/** The sets the input line and the title go to: a default spec for their class is installed. */
export function writingSugars(sugars: readonly Sugar[], cellSpecs: readonly CellSpec[]): Sugar[] {
	return sugars.filter((s) => defaultSpecOf(cellSpecs, s.class) !== null);
}

/** The input line's placeholder: the first writing set's, else the core's own. */
export function inputHint(
	sugars: readonly Sugar[],
	cellSpecs: readonly CellSpec[],
): string | undefined {
	return writingSugars(sugars, cellSpecs).find((s) => s.inputHint)?.inputHint;
}

/** The hints a cell's markdown editor draws while it has the caret: the first bound set's that has any. */
export function editorHint(
	sugars: readonly Sugar[],
	classes: readonly string[],
): { blank?: string; tail?: string } | undefined {
	return sugars.find((s) => s.editorHint && classes.includes(s.class))?.editorHint;
}

/** What the core does when no sugar claims an intent. The plane supplies it. */
export type CoreDefaults = {
	/** Today's step out of a cell, up or down. False with nowhere to go. */
	step: (cell: string, dir: ExitDir) => boolean;
	/** Into the cells from the title. False with nowhere to land. */
	enterTop: () => boolean;
};

export type Router = {
	editor: (cell: string, i: MarkdownIntent) => boolean;
	input: (after: string | null, i: InputIntent, api: PlaneApi) => boolean;
	title: (i: TitleIntent) => boolean;
};

/** The routing for one render of one plane. */
export function router({
	sugars,
	cellSpecs,
	editable,
	cells,
	api,
	core,
}: {
	sugars: readonly Sugar[];
	cellSpecs: readonly CellSpec[];
	editable: boolean;
	cells: readonly { id: string; classes: readonly string[] }[];
	api: PlaneApi;
	core: CoreDefaults;
}): Router {
	const writing = writingSugars(sugars, cellSpecs);

	return {
		editor(cell, i) {
			if (!editable) return false;
			const classes = cells.find((c) => c.id === cell)?.classes ?? [];
			for (const s of sugars) {
				if (s.onEditor && classes.includes(s.class) && s.onEditor(cell, i, api)) return true;
			}
			if (i.kind === "leave" && !i.extend) {
				return core.step(cell, i.dir === "up" || i.dir === "left" ? "up" : "down");
			}
			return false;
		},

		// True when a set claimed it. The core default is the line's own
		// (./input/useGhosts.ts), since only the line knows where its menu
		// opens. The line hands in its own api: see `lineApi` in ./Plane.tsx.
		input(after, i, lineApi) {
			if (!editable) return false;
			for (const s of writing) if (s.onInput?.(after, i, lineApi)) return true;
			return false;
		},

		title(i) {
			if (!editable) return false;
			for (const s of writing) if (s.onTitle?.(i, api)) return true;
			if (i.kind === "enter" && !i.end) return false;
			return core.enterTop();
		},
	};
}
