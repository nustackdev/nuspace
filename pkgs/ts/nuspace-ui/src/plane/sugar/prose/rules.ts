// The prose set's rules: one table per place an intent comes from.
//
// A rule answers one kind of intent. `when` asks whether it applies, of the
// plane API and the cell's markdown handle only, never of the DOM, the caret or
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
//   R8  the arrows cross into the prose cell that way, or the title, from
//       a prose cell or an empty input line, and stop at the island's edge
//   R10 Shift+arrow at the edge spills into cell selection
//   merge  Backspace at the very start of a prose cell with text joins it
//          onto the end of the prose cell above
//   split  Cmd+Enter with text after the caret moves that text into a new
//          prose cell below
//
// Merge and split are each other's way back. Both are composed from the
// handle's own commands (append, tail, cut) and the plane's create and
// remove, ordered so that the text is always in at least one cell: merge
// appends and saves above before it removes, split hands the tail to the
// new cell and saves the cut here only once that cell has stored it.
//
// R9, a text drag out of a cell, is the core's range select: a pointer
// press is not an intent a markdown editor reports.
//
// The arrows keep to an island: a run of the title, prose cells and input
// lines with nothing else in between, read as one document. Leaving it is
// not an arrow's to do. At its edge, a cell of another class that way, the
// caret stays, as at the end of a document; Shift+arrow (R10) is the way
// out into cell selection, Escape and a click the others.

import type { FocusAt, LeaveDir, MarkdownIntent } from "@nustackdev/ui-kit";
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
	/** Whether it applies, asked of the plane and the handle only. */
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

const doc = rule<MarkdownIntent, string>();
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
 * What R8 meets leaving `cell` that way: the prose cell there or the title
 * above the top one (a target), a cell of another class (`edge`, the
 * island ends), or null when it is not R8's to say: an input line in
 * between, which the core's step goes into, or nothing at all.
 */
function across(
	api: PlaneApi,
	cell: string,
	dir: LeaveDir,
	x: number,
): FocusTarget | "edge" | null {
	const b = api.beside(cell, backward(dir) ? "up" : "down");
	if (b.line) return null;
	if (b.cell) return prose(api, b.cell) ? { cell: b.cell, at: landing(dir, x) } : "edge";
	return b.title ? { title: "end" } : null;
}

/**
 * The cell an input line after `after` (null: the top) meets that way: the
 * cell it hangs off going up, the next one going down. Its id when it is
 * prose, `edge` when it is of another class, null when there is none.
 */
function toward(api: PlaneApi, after: string | null, dir: "up" | "down"): string | "edge" | null {
	const i = after === null ? -1 : api.index(after);
	if (after !== null && i < 0) return null;
	const id = dir === "up" ? after : api.cells[i + 1]?.id;
	if (!id) return null;
	return prose(api, id) ? id : "edge";
}

/** Where the caret goes when `cell` is removed from under it: the end of the cell above, else the title. */
export function above(api: PlaneApi, cell: string): FocusTarget {
	const up = api.beside(cell, "up").cell;
	return up ? { cell: up, at: "end" } : { title: "end" };
}

/* ============================== the tables =============================== */

/** Intents from a prose cell's markdown editor, the cell's id at `at`. */
export const editorRules: Rule<MarkdownIntent, string>[] = [
	// R2. Backspace with nothing written removes the cell, the caret going to
	// the end of whatever cell is above, or the title for the top one. Back:
	// R7 at the end of the cell above opens a line, and typing there is R1.
	doc({
		rule: "R2",
		on: "erase",
		when: ({ at, i, api }) => i.dir === "back" && api.editor(at)?.blank() === true,
		run: ({ at, api }) => api.remove([at], above(api, at)),
		back: "R7 + R1",
	}),
	// Merge. Backspace at the very start of a cell with text (the editor
	// reports it only there), with a prose cell right above (no input line
	// in between): its text goes onto the end of that one, joined at a
	// paragraph break, the only join markdown can store, and this cell goes.
	// The caret goes to the join at once, where append left the selection;
	// into a blank cell above, append replaces its empty paragraph and the
	// caret is at the text's start. The top cell, or another class above,
	// and Backspace does nothing. Back: split at the join.
	//
	// One move on screen: the text joins above and this cell goes out of
	// sight in the same frame (`withdraw`). In the store it is two, in order:
	// the delete is sent only once the one above provably took the text (its
	// markdown changed) and Nu has read that back (`saved`), so the text is
	// never in neither cell. Written to in the meantime, this cell is no
	// longer what was appended, or the one above no longer holds it, or the
	// one above went: this cell comes back, the text in both rather than an
	// edit lost with the delete.
	doc({
		rule: "merge",
		on: "erase",
		when: ({ at, i, api }) => {
			const b = api.beside(at, "up");
			return (
				i.dir === "back" &&
				!b.line &&
				b.cell !== null &&
				prose(api, b.cell) &&
				api.editor(b.cell) !== null
			);
		},
		run: ({ at, api }) => {
			const up = api.beside(at, "up").cell;
			const into = up ? api.editor(up) : null;
			const from = api.editor(at);
			if (!up || !into || !from) return;
			const text = from.markdown();
			const before = into.markdown();
			into.append(text);
			// It took nothing (read-only meanwhile, or nothing to add): stop here.
			if (into.markdown() === before) return;
			into.commit();
			api.focus({ cell: up, at: "kept" });
			const out = api.withdraw([at]);
			into.saved(
				() => {
					const here = api.editor(at);
					const moved = here?.markdown() === text && into.markdown().includes(text.trim());
					if (moved) out.remove();
					else out.restore();
				},
				() => out.restore(),
			);
		},
		back: "split",
	}),

	// R6. `/` in a blank cell (the editor reports it only there) puts the
	// menu in its place, and a pick replaces it. Back: Escape brings the cell
	// back with the caret in it.
	doc({
		rule: "R6",
		on: "slash",
		when: ({ at, api }) => api.editor(at)?.blank() === true,
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
	// Split. Cmd+Enter with text after the caret (at the very start that is
	// all of it, leaving this cell blank; in a list it cuts the list): a cell
	// from the prose default below, handed the text after the caret, the
	// caret at its start. Back: merge, Backspace at the new cell's start.
	//
	// One move on screen: the new cell shows holding the tail in the same
	// frame the tail leaves here (the handle's held `cut`). In the store it
	// is two, in order: this cell saves the cut only once the new cell's
	// text is in (`saved`), so the tail is never in neither. The new cell
	// gone or rewritten before then, the cut is undone. A cell that never
	// takes the tail, or holds something else, leaves it here uncut. And
	// written here meanwhile (another tab, a program), what follows the
	// caret is no longer what was handed over, so nothing is cut: the text
	// in both cells rather than in neither.
	doc({
		rule: "split",
		on: "break",
		when: ({ i, api }) => i.at === "mid" && api.defaultSpec(PROSE) !== null,
		run: ({ at, api }) => {
			const spec = api.defaultSpec(PROSE);
			const from = api.editor(at);
			if (!spec || !from) return;
			const tail = from.tail();
			api.create({ after: at }, spec, {
				at: "start",
				markdown: tail,
				landed: (into) => {
					// Compared as the editor writes it back, which may differ from
					// the cut only in trailing blank lines. Any other difference
					// leaves both: a text in two cells is a nuisance, in none a loss.
					if (into.blank() || into.markdown().trim() !== tail.trim()) return;
					const here = api.editor(at);
					if (!here || here.tail() !== tail) return;
					into.commit();
					const cut = here.cut();
					into.saved(
						// The new cell no longer holding the tail (its text deleted or
						// rewritten meanwhile): the tail comes back here.
						() => (into.markdown().includes(tail.trim()) ? cut.keep() : cut.undo()),
						() => cut.undo(),
					);
				},
			});
		},
		back: "merge",
	}),

	// R8. An arrow out of the text lands in the prose cell that way, under
	// the caret going up or down, or in the title above the top cell. A cell
	// of another class that way is the island's edge: the caret stays. Back:
	// the opposite arrow, which is R8 again from the other side.
	doc({
		rule: "R8",
		on: "leave",
		when: ({ at, i, api }) => !i.extend && across(api, at, i.dir, i.x) !== null,
		run: ({ at, i, api }) => {
			const to = across(api, at, i.dir, i.x);
			if (to && to !== "edge") api.focus(to);
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
	// as the person's own keys once its editor is there, the keys typed
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
	// R8 from the line: leaving it empty (Up, Left or Backspace up, Down or
	// Right down) puts the caret in the prose cell that way, at its end above
	// and its start below, so the line sits in the writing flow. A cell of
	// another class that way is the island's edge: the caret stays. No cell,
	// the core's: the title above the top, nothing below the end. Back: the
	// opposite arrow, R8 from that cell, into the end line; a summoned line
	// went as the caret left it.
	line({
		rule: "R8",
		on: "leave",
		when: ({ at, i, api }) => toward(api, at, i.dir) !== null,
		run: ({ at, i, api }) => {
			const to = toward(api, at, i.dir);
			if (to && to !== "edge") api.focus({ cell: to, at: i.dir === "up" ? "end" : "start" });
		},
		back: "R8",
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
	// cell on top (the title has no x to land under). A cell of another class
	// on top is the island's edge: the caret stays. An input line summoned
	// above the top cell, or an empty plane's end line, the core goes into.
	// Back: R8, Up or Left at that cell's start.
	head({
		rule: "R8",
		on: "leave",
		when: ({ api }) => {
			const top = api.cells[0];
			return top !== undefined && !api.beside(top.id, "up").line;
		},
		run: ({ api }) => {
			const top = api.cells[0];
			if (top && prose(api, top.id)) api.focus({ cell: top.id, at: "start" });
		},
		back: "R8",
	}),
];
