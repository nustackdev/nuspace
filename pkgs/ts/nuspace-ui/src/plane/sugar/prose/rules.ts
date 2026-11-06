// The prose set's rules: one table per place an intent comes from.
//
// A rule answers one kind of intent. `when` asks whether it applies, of the
// plane API and the cell's document only, never of the DOM, the caret or
// which spec made a cell. `run` acts through the same two. The first rule of
// the intent's kind whose `when` holds runs, and the set answers true; none
// does and the core does its own default (../../intents.ts). So declining is
// always safe: a rule that does not apply leaves the key to the plane or the
// editor, exactly as if no sugar were there.
//
// Every rule has its way back, written next to it (`back`, and why in the
// comment above it). A forward rule whose inverse would need convoluted
// logic does not go in. The names are the interaction table's (task-162):
//
//   R1  the input line: typed text or Enter makes a prose cell holding it
//   R2  Backspace in a blank prose cell removes it, the caret above
//   R5  Enter in the title makes a prose cell at the top
//   R6  `/` in a blank prose cell stands the menu in for it
//   R7  Cmd+Enter at the end of the text opens an input line below
//   R8  the arrows cross into the prose cell that way, or the title
//   R10 Shift+arrow at the edge spills into cell selection
//
// R9, a text drag out of a cell, is the core's range select: a pointer
// press is not an intent a document reports. Merge and split are the next
// two rows (task-162 phase 5); until they land, Backspace at the start of a
// prose cell with text and Cmd+Enter mid-text fall through to the core,
// which does nothing with either.

import type { DocIntent, FocusAt, LeaveDir } from "@nustackdev/ui-kit";
import type { FocusTarget, PlaneApi } from "../../api";
import type { InputIntent, TitleIntent } from "../../intents";

/** The class this set is bound to. */
export const PROSE = "prose";

/** What a rule is asked: where the intent came from, the intent, the plane. */
export type Ctx<I, At> = { at: At; i: I; api: PlaneApi };

// `when` and `run` are methods, not function fields, so a rule written over
// one kind of intent is still a rule over all of them (`One` below).
export interface Rule<I extends { kind: string }, At> {
	/** Its name in the interaction table. */
	rule: string;
	/** The kind of intent it answers. */
	on: I["kind"];
	/** Whether it applies, asked of the plane and the document only. */
	when(x: Ctx<I, At>): boolean;
	run(x: Ctx<I, At>): void;
	/** Its way back: the rule or gesture that undoes it. */
	back: string;
}

/** A rule over one kind of intent, seeing that kind only. */
type One<I extends { kind: string }, At, K extends I["kind"]> = Rule<
	Extract<I, { kind: K }>,
	At
> & {
	on: K;
};

const rule =
	<I extends { kind: string }, At>() =>
	<K extends I["kind"]>(r: One<I, At, K>): Rule<I, At> =>
		r;

const doc = rule<DocIntent, string>();
const line = rule<InputIntent, string | null>();
const head = rule<TitleIntent, null>();

/** The first rule of the intent's kind that applies, run. True when one did. */
export function answer<I extends { kind: string }, At>(
	rules: readonly Rule<I, At>[],
	x: Ctx<I, At>,
): boolean {
	const r = rules.find((r) => r.on === x.i.kind && r.when(x));
	if (!r) return false;
	r.run(x);
	return true;
}

/* ============================== reads ==================================== */

/** Whether cell `id` keeps the prose class. */
function prose(api: PlaneApi, id: string): boolean {
	return api.cells.find((c) => c.id === id)?.classes.includes(PROSE) ?? false;
}

function backward(dir: LeaveDir): boolean {
	return dir === "up" || dir === "left";
}

/** Where the caret lands crossing into a cell: under x going up or down, at the near edge sideways. */
function landing(dir: LeaveDir, x: number): FocusAt {
	if (dir === "up") return { x, edge: "last" };
	if (dir === "down") return { x, edge: "first" };
	return dir === "left" ? "end" : "start";
}

/**
 * Where R8 takes the caret leaving `cell` that way: the prose cell there,
 * or the title above the top one. Null when it is not R8's to say: an
 * input line in between, a cell of another class, or nothing at all. The
 * core's step goes into the line or the cell, as it always has.
 */
function across(api: PlaneApi, cell: string, dir: LeaveDir, x: number): FocusTarget | null {
	const b = api.beside(cell, backward(dir) ? "up" : "down");
	if (b.line) return null;
	if (b.cell) return prose(api, b.cell) ? { cell: b.cell, at: landing(dir, x) } : null;
	return b.title ? { title: "end" } : null;
}

/** Where the caret goes when `cell` is removed from under it: the end of the cell above, else the title. */
export function above(api: PlaneApi, cell: string): FocusTarget {
	const up = api.beside(cell, "up").cell;
	return up ? { cell: up, at: "end" } : { title: "end" };
}

/* ============================== the tables =============================== */

/** Intents from a prose cell's document, the cell's id at `at`. */
export const documentRules: Rule<DocIntent, string>[] = [
	// R2. Backspace with nothing written removes the cell, the caret going to
	// the end of whatever cell is above, or the title for the top one. Back:
	// R7 at the end of the cell above opens a line, and typing there is R1.
	doc({
		rule: "R2",
		on: "erase",
		when: ({ at, i, api }) => i.dir === "back" && api.document(at)?.blank() === true,
		run: ({ at, api }) => api.remove([at], above(api, at)),
		back: "R7 + R1",
	}),
	// Merge (phase 5) goes here: erase back, not blank, a prose cell above.

	// R6. `/` in a blank cell (the editor reports it only there) puts the
	// menu in its place, and a pick replaces it. Back: Escape brings the cell
	// back with the caret in it.
	doc({
		rule: "R6",
		on: "slash",
		when: ({ at, api }) => api.document(at)?.blank() === true,
		run: ({ at, api }) => api.standIn(at),
		back: "Escape",
	}),

	// R7. Cmd+Enter with nothing but empty lines after the caret opens an
	// input line below, remembering the caret. Back: Escape there puts the
	// caret back where it was.
	doc({
		rule: "R7",
		on: "break",
		when: ({ i }) => i.at === "end",
		run: ({ at, api }) => api.openInput(at, { cell: at, at: "kept" }),
		back: "Escape",
	}),
	// Split (phase 5) goes here: break mid-text.

	// R8. An arrow out of the text lands in the prose cell that way, under
	// the caret going up or down, or in the title above the top cell. Back:
	// the opposite arrow, which is R8 again from the other side.
	doc({
		rule: "R8",
		on: "leave",
		when: ({ at, i, api }) => !i.extend && across(api, at, i.dir, i.x) !== null,
		run: ({ at, i, api }) => {
			const to = across(api, at, i.dir, i.x);
			if (to) api.focus(to);
		},
		back: "R8",
	}),

	// R10. Shift+arrow with the selection's head at the edge selects this
	// cell and the next one that way, any class, anchored here, and Shift
	// goes on as cell selection. Back: Escape, or a click back into the text.
	doc({
		rule: "R10",
		on: "leave",
		when: ({ at, i, api }) =>
			i.extend && api.beside(at, backward(i.dir) ? "up" : "down").cell !== null,
		run: ({ at, i, api }) => {
			const next = api.beside(at, backward(i.dir) ? "up" : "down").cell;
			if (next) api.select(backward(i.dir) ? [next, at] : [at, next], at);
		},
		back: "Escape",
	}),
];

/** Typed text or Enter on the input line, the cell it sits after at `at`. */
export const inputRules: Rule<InputIntent, string | null>[] = [
	// R1. Typing writes: a cell from the prose default, the text typed into it
	// as the person's own keys once its document is there, the keys typed
	// meanwhile going along. Back: delete the text, then R2.
	line({
		rule: "R1",
		on: "text",
		when: ({ api }) => api.defaultSpec(PROSE) !== null,
		run: ({ at, i, api }) => {
			const spec = api.defaultSpec(PROSE);
			if (spec) api.create({ after: at }, spec, { at: "end", text: i.text });
		},
		back: "R2",
	}),
	// R1 with nothing typed: an empty prose cell, the caret in it. Back: R2.
	line({
		rule: "R1",
		on: "enter",
		when: ({ api }) => api.defaultSpec(PROSE) !== null,
		run: ({ at, api }) => {
			const spec = api.defaultSpec(PROSE);
			if (spec) api.create({ after: at }, spec, { at: "end" });
		},
		back: "R2",
	}),
];

/** Enter in the title, or leaving it at its end. */
export const titleRules: Rule<TitleIntent, null>[] = [
	// R5. Enter in the title starts an empty prose cell at the top, the title
	// left whole. Back: R2 in it, which puts the caret back at the title's end.
	head({
		rule: "R5",
		on: "enter",
		when: ({ api }) => api.defaultSpec(PROSE) !== null,
		run: ({ api }) => {
			const spec = api.defaultSpec(PROSE);
			if (spec) api.create({ after: null }, spec, { at: "start" });
		},
		back: "R2",
	}),
	// R8 from the title: Down or Right at its end goes to the start of a prose
	// cell on top (the title has no x to land under). Anything else on top,
	// the core goes into it. Back: R8, Up or Left at that cell's start.
	head({
		rule: "R8",
		on: "leave",
		when: ({ api }) => {
			const top = api.cells[0];
			return top !== undefined && prose(api, top.id);
		},
		run: ({ api }) => api.focus({ cell: api.cells[0].id, at: "start" }),
		back: "R8",
	}),
];
