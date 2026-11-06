// The prose set on a real plane in jsdom, one test per interaction table row
// (task-162) the set decides, named `row N` with the table's test name. The
// documents are fakes registered in the kit registry (../../plane.testing),
// so what is checked is what the set asks of the plane and the documents,
// not what an editor does with it: that half is the kit's browser tests.
//
// Rows the set declines are here too, where declining is the rule: the
// core's default runs, or nothing does. Merge and split are not built yet,
// so their keys must fall through harmlessly.

import { pathKey, register, registerDocument } from "@nustackdev/ui-kit";
import { act, useEffect } from "react";
import { describe, expect, it, vi } from "vitest";
import {
	cell,
	draw,
	endLine,
	fakeDoc,
	lines,
	menu,
	mountDoc,
	notify,
	onTitle,
	ops,
	PLAIN,
	planeRoot,
	press,
	render,
	row,
	selected,
	title,
	typeInto,
	VIEWER,
	WITH_DEFAULT,
} from "../../plane.testing";
import { readEditor } from "../../state";
import type { Cell } from "../../types";
import { type Sugar, sugars } from "..";
import { prose } from ".";
import { NEW_CELL_HINT, WRITE_HINT } from "./hints";
import { documentRules, inputRules, type Rule, titleRules } from "./rules";

/** A view that is a document with something to focus, as an editor is. */
let focusDoc: ReturnType<typeof fakeDoc> | null = null;
register("TestFocusDoc", {
	component: ({ path }: { path: string[] }) => {
		// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
		useEffect(() => (focusDoc ? registerDocument(path, focusDoc.doc) : undefined), [pathKey(path)]);
		// biome-ignore lint/a11y/noNoninteractiveTabindex: it stands for an editor, which takes focus.
		return <div tabIndex={0} data-focus-doc="" />;
	},
});

/** A plane with the prose set and the prose default installed. */
function plane(
	cells: Cell[],
	opts: { specs?: typeof PLAIN; editable?: boolean; title?: boolean; sugars?: Sugar[] } = {},
) {
	render(cells, { specs: WITH_DEFAULT, sugars: [prose], ...opts });
}

const leave = (dir: "up" | "down" | "left" | "right", x = 0, extend = false) =>
	({ kind: "leave", dir, extend, x }) as const;
const created = () => notify.mock.calls.filter(([op]) => op === "cell.create").map(([, a]) => a);
const plus = (id: string) =>
	act(() =>
		row(id).querySelector<HTMLButtonElement>("button[aria-label='Add a line below']")?.click(),
	);

describe("the registry", () => {
	it("names the prose set, the one set there is", () => {
		expect(sugars).toEqual([prose]);
	});
});

describe("the rule table", () => {
	const all = [...documentRules, ...inputRules, ...titleRules] as Rule<{ kind: string }, unknown>[];

	it("names its way back for every rule, and every rule it names is one", () => {
		const names = new Set(all.map((r) => r.rule));
		for (const r of all) {
			expect(r.back.trim(), r.rule).not.toBe("");
			for (const named of r.back.match(/R\d+/g) ?? []) expect(names, r.rule).toContain(named);
		}
	});

	it("is R1 to R10, merge and split left for the next phase", () => {
		expect([...new Set(all.map((r) => r.rule))].sort()).toEqual(
			["R1", "R10", "R2", "R5", "R6", "R7", "R8"].sort(),
		);
	});
});

describe("A. the input line", () => {
	it("row 1 r1_type_creates_default: typing makes a prose cell that types it in", () => {
		plane([cell("a")]);
		act(() => endLine().focus());
		typeInto(endLine(), "h");
		expect(created()).toEqual([expect.objectContaining({ name: "text", index: 1 })]);
		expect(menu()).toBeNull();
		const id = created()[0].cell_id as string;
		plane([cell("a"), cell(id)]);
		const d = mountDoc(id);
		expect(d.doc.focus).toHaveBeenCalledWith("end");
		expect(d.doc.type).toHaveBeenCalledExactlyOnceWith("h");
	});

	it("row 2 input_char_searches_without_default: no default, the menu searches", () => {
		plane([], { specs: PLAIN });
		typeInto(endLine(), "h");
		expect(notify).not.toHaveBeenCalled();
		expect(menu()).not.toBeNull();
	});

	it("row 3 r1_enter_creates_empty: Enter makes an empty prose cell, the caret in it", () => {
		plane([]);
		press(endLine(), "Enter");
		expect(created()).toEqual([expect.objectContaining({ name: "text", index: 0 })]);
		const id = created()[0].cell_id as string;
		plane([cell(id)]);
		const d = mountDoc(id);
		expect(d.doc.focus).toHaveBeenCalledWith("end");
		expect(d.doc.type).not.toHaveBeenCalled();
	});

	it("row 4 input_enter_noop_without_default: no default, Enter does nothing", () => {
		plane([], { specs: PLAIN });
		press(endLine(), "Enter");
		expect(notify).not.toHaveBeenCalled();
	});

	it("row 13 top_line_up_to_title: Up or Backspace from the line on an empty plane goes to the title end", () => {
		plane([]);
		press(endLine(), "ArrowUp");
		expect(onTitle).toHaveBeenLastCalledWith("end");
		onTitle.mockClear();
		press(endLine(), "Backspace");
		expect(onTitle).toHaveBeenLastCalledWith("end");
	});

	it("row 18 menu_typing_filters: with the menu open typing filters, never R1", () => {
		plane([]);
		press(endLine(), "/");
		typeInto(endLine(), "te");
		expect(notify).not.toHaveBeenCalled();
		expect(endLine().value).toBe("te");
	});

	it("row 20 input_hint_by_default: the line says what typing does", () => {
		plane([]);
		expect(endLine().placeholder).toBe(WRITE_HINT);
		plane([], { specs: PLAIN });
		expect(endLine().placeholder).toBe("Press / for cells");
	});

	it("row 21 r1_keys_while_pending_go_along: keys typed while the cell is on its way go with it", () => {
		plane([]);
		act(() => endLine().focus());
		typeInto(endLine(), "h");
		typeInto(endLine(), "hi");
		press(endLine(), "Enter");
		typeInto(endLine(), "x");
		const id = created()[0].cell_id as string;
		plane([cell(id)]);
		const d = mountDoc(id);
		expect(d.doc.type).toHaveBeenCalledExactlyOnceWith("hi\nx");
		expect(created()).toHaveLength(1);
	});

	it("row 23 r1_text_lands_caret_stays_away: the text lands, the caret is not pulled back", () => {
		plane([]);
		act(() => endLine().focus());
		typeInto(endLine(), "hi");
		act(() => endLine().blur());
		const id = created()[0].cell_id as string;
		plane([cell(id)]);
		const d = mountDoc(id);
		expect(d.doc.type).toHaveBeenCalledWith("hi");
		expect(d.doc.focus).not.toHaveBeenCalled();
	});

	it("row 24 r1_no_register_keeps_text: a cell that fails gives the text back to the line", () => {
		plane([]);
		act(() => endLine().focus());
		typeInto(endLine(), "hi");
		const id = created()[0].cell_id as string;
		plane([cell(id, ["prose"], "boom")]);
		expect(endLine().value).toBe("hi");
		expect(readEditor(VIEWER, "p1").requests).toEqual([]);
	});

	it("row 25 read_only_no_sugar: a read-only plane routes nothing to the set", () => {
		plane([cell("a"), cell("b")], { editable: false });
		expect(lines()).toHaveLength(0);
		const b = mountDoc("b", fakeDoc(true));
		expect(b.say({ kind: "erase", dir: "back" })).toBe(false);
		expect(b.say(leave("up"))).toBe(false);
		expect(title({ kind: "enter", end: true })).toBe(false);
		expect(notify).not.toHaveBeenCalled();
	});
});

describe("B. the title", () => {
	it("row 26 r5_title_enter_creates_top: Enter anywhere makes a prose cell at the top", () => {
		plane([cell("a")]);
		expect(title({ kind: "enter", end: false })).toBe(true);
		expect(created()).toEqual([expect.objectContaining({ name: "text", index: 0 })]);
		const id = created()[0].cell_id as string;
		plane([cell(id), cell("a")]);
		expect(mountDoc(id).doc.focus).toHaveBeenCalledWith("start");
	});

	it("row 27 title_enter_core_at_end: no default, Enter at the end goes into the cells", () => {
		plane([cell("a", [])], { specs: PLAIN });
		expect(title({ kind: "enter", end: true })).toBe(true);
		expect(selected()).toEqual(["a"]);
		expect(notify).not.toHaveBeenCalled();
	});

	it("row 29 r8_title_down_into_prose: Down at the end lands at the start of the prose cell on top", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a");
		expect(title({ kind: "leave", dir: "down" })).toBe(true);
		expect(a.doc.focus).toHaveBeenCalledWith("start");
		expect(selected()).toEqual([]);
	});

	it("row 30 r8_title_right_into_prose: Right at the end too", () => {
		plane([cell("a")]);
		const a = mountDoc("a");
		expect(title({ kind: "leave", dir: "right" })).toBe(true);
		expect(a.doc.focus).toHaveBeenCalledWith("start");
	});

	it("row 31 title_leave_into_non_prose: another class on top, the core selects it", () => {
		plane([cell("a", []), cell("b")]);
		expect(title({ kind: "leave", dir: "down" })).toBe(true);
		expect(selected()).toEqual(["a"]);
	});

	it("row 32 title_leave_empty_plane: nothing on top, the end line", () => {
		plane([]);
		expect(title({ kind: "leave", dir: "down" })).toBe(true);
		expect(document.activeElement).toBe(endLine());
	});

	it("row 38 r8_top_up_to_title: Up on the top cell's first line goes to the title end", () => {
		plane([cell("a"), cell("b")]);
		expect(mountDoc("a").say(leave("up", 30))).toBe(true);
		expect(onTitle).toHaveBeenCalledWith("end");
	});

	it("row 39 r8_top_left_to_title: Left at its start too", () => {
		plane([cell("a")]);
		expect(mountDoc("a").say(leave("left"))).toBe(true);
		expect(onTitle).toHaveBeenCalledWith("end");
	});

	it("row 38, no title: the top cell keeps the key", () => {
		plane([cell("a")], { title: false });
		expect(mountDoc("a").say(leave("up"))).toBe(false);
	});
});

describe("C. a blank prose cell", () => {
	it("row 41 r2_remove_to_prose_above: Backspace removes it, the caret at the end of the one above", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", fakeDoc(false));
		expect(mountDoc("b").say({ kind: "erase", dir: "back" })).toBe(true);
		expect(ops()).toEqual([["cell.delete", "b"]]);
		expect(row("b").hidden).toBe(true);
		expect(a.doc.focus).toHaveBeenCalledWith("end");
	});

	it("row 42 r2_remove_to_non_prose_above: any cell above takes it; with no document, it is selected", () => {
		plane([cell("a", []), cell("b")]);
		expect(mountDoc("b").say({ kind: "erase", dir: "back" })).toBe(true);
		expect(ops()).toEqual([["cell.delete", "b"]]);
		expect(selected()).toEqual(["a"]);
		expect(onTitle).not.toHaveBeenCalled();
	});

	it("row 43 r2_top_to_title: the top one goes to the title end", () => {
		plane([cell("a"), cell("b")]);
		expect(mountDoc("a").say({ kind: "erase", dir: "back" })).toBe(true);
		expect(ops()).toEqual([["cell.delete", "a"]]);
		expect(onTitle).toHaveBeenCalledWith("end");
	});

	it("row 44 r2_top_no_title: with no title the plane takes the keyboard", () => {
		plane([cell("a")], { title: false });
		expect(mountDoc("a").say({ kind: "erase", dir: "back" })).toBe(true);
		expect(document.activeElement).toBe(planeRoot());
	});

	it("row 45 r2_only_cell: the only cell goes, title end, the end line is all there is", () => {
		plane([cell("a")]);
		mountDoc("a").say({ kind: "erase", dir: "back" });
		expect(onTitle).toHaveBeenCalledWith("end");
		plane([]);
		expect(lines()).toHaveLength(1);
		expect(endLine().placeholder).toBe(WRITE_HINT);
	});

	it("row 41, written: Backspace in a cell with text is not R2", () => {
		plane([cell("a"), cell("b")]);
		expect(mountDoc("b", fakeDoc(false)).say({ kind: "erase", dir: "back" })).toBe(false);
		expect(notify).not.toHaveBeenCalled();
	});

	it("row 46 erase_forward_noop: Delete does nothing in v0", () => {
		plane([cell("a"), cell("b")]);
		expect(mountDoc("a").say({ kind: "erase", dir: "forward" })).toBe(false);
		expect(notify).not.toHaveBeenCalled();
	});

	it("row 47 r6_slash_stands_in: `/` puts the menu in its place", () => {
		plane([cell("a"), cell("b")]);
		expect(mountDoc("a").say({ kind: "slash" })).toBe(true);
		expect(row("a").hidden).toBe(true);
		expect(menu()).not.toBeNull();
	});

	it("row 49 r6_pick_replaces: a pick takes its place", () => {
		plane([cell("a"), cell("b")]);
		mountDoc("a").say({ kind: "slash" });
		press(lines()[0], "Enter");
		expect(ops().map(([op]) => op)).toEqual(["cell.create", "cell.delete"]);
		expect(notify.mock.calls[0][1]).toMatchObject({ index: 1 });
		expect(notify.mock.calls[1][1]).toEqual({ cell_id: "a" });
	});

	it("row 50 r6_esc_brings_back: Escape brings the cell back, the caret at its start", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a");
		a.say({ kind: "slash" });
		press(lines()[0], "Escape");
		expect(row("a").hidden).toBe(false);
		expect(a.doc.focus).toHaveBeenCalledWith("start");
		expect(notify).not.toHaveBeenCalled();
	});

	it("row 52 r7_opens_line_below: Cmd+Enter at the end opens a line below", () => {
		plane([cell("a"), cell("b")]);
		expect(mountDoc("a").say({ kind: "break", at: "end" })).toBe(true);
		expect(lines()).toHaveLength(2);
		expect(document.activeElement).toBe(lines()[0]);
	});

	it("row 6 r7_esc_returns_caret: Escape there puts the caret back where it was", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a");
		a.say({ kind: "break", at: "end" });
		press(lines()[0], "Escape");
		expect(lines()).toHaveLength(1);
		expect(a.doc.focus).toHaveBeenCalledWith("kept");
	});

	it("row 53 r7_last_cell_uses_end_line: in the last cell, the end line, which stays on Escape", () => {
		plane([cell("a")]);
		const a = mountDoc("a");
		a.say({ kind: "break", at: "end" });
		expect(lines()).toHaveLength(1);
		expect(document.activeElement).toBe(endLine());
		press(endLine(), "Escape");
		expect(lines()).toHaveLength(1);
		expect(a.doc.focus).toHaveBeenCalledWith("kept");
	});

	it("rows 54-57 r8_blank_*: the arrows cross a blank cell like any other", () => {
		plane([cell("a"), cell("b"), cell("c")]);
		const a = mountDoc("a");
		const b = mountDoc("b");
		const c = mountDoc("c");
		b.say(leave("up", 12));
		expect(a.doc.focus).toHaveBeenLastCalledWith({ x: 12, edge: "last" });
		b.say(leave("down", 12));
		expect(c.doc.focus).toHaveBeenLastCalledWith({ x: 12, edge: "first" });
		b.say(leave("left"));
		expect(a.doc.focus).toHaveBeenLastCalledWith("end");
		b.say(leave("right"));
		expect(c.doc.focus).toHaveBeenLastCalledWith("start");
	});

	it("row 63 no_sugar_for_classless_doc: a document in a classless cell gets none of it", () => {
		plane([cell("a"), cell("b", [])]);
		const b = mountDoc("b");
		expect(b.say({ kind: "erase", dir: "back" })).toBe(false);
		expect(b.say({ kind: "slash" })).toBe(false);
		expect(b.say({ kind: "break", at: "end" })).toBe(false);
		expect(notify).not.toHaveBeenCalled();
		expect(lines()).toHaveLength(1);
	});
});

describe("C. hints, row 59", () => {
	it("draws the blank and last-line hints while the caret is in a prose cell, and clears them as it leaves", async () => {
		const d = fakeDoc();
		focusDoc = d;
		plane([cell("a")]);
		await draw("a", "TestFocusDoc");
		focusDoc = null;
		const drawn = row("a").querySelector<HTMLElement>("[data-focus-doc]") as HTMLElement;
		act(() => drawn.focus());
		expect(d.doc.hint).toHaveBeenCalledWith(WRITE_HINT, "blank");
		expect(d.doc.hint).toHaveBeenCalledWith(NEW_CELL_HINT, "tail");
		act(() => endLine().focus());
		expect(d.doc.hint).toHaveBeenCalledWith(null, "blank");
		expect(d.doc.hint).toHaveBeenLastCalledWith(null, "tail");
	});

	it("draws none in a classless cell's document, or with no set", async () => {
		for (const opts of [
			{ classes: [] as string[], sugars: [prose] },
			{ classes: ["prose"], sugars: [] },
		]) {
			const d = fakeDoc();
			focusDoc = d;
			plane([cell("a", opts.classes)], { sugars: opts.sugars });
			await draw("a", "TestFocusDoc");
			focusDoc = null;
			act(() => row("a").querySelector<HTMLElement>("[data-focus-doc]")?.focus());
			expect(d.doc.hint).not.toHaveBeenCalledWith(WRITE_HINT, "blank");
			act(() => endLine().focus());
		}
	});
});

describe("D. arrows across prose cells", () => {
	it("row 64 r8_up_at_x: Up on the first line lands under x on the last line above", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", fakeDoc(false));
		expect(mountDoc("b", fakeDoc(false)).say(leave("up", 40))).toBe(true);
		expect(a.doc.focus).toHaveBeenCalledWith({ x: 40, edge: "last" });
		expect(selected()).toEqual([]);
	});

	it("row 65 leave_up_into_non_prose: another class above, the core steps into it", () => {
		plane([cell("a", []), cell("b")]);
		expect(mountDoc("b").say(leave("up", 40))).toBe(true);
		expect(selected()).toEqual(["a"]);
	});

	it("row 66 leave_up_into_line: a summoned line above is landed in first", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a");
		const b = mountDoc("b");
		plus("a");
		expect(lines()).toHaveLength(2);
		expect(b.say(leave("up", 40))).toBe(true);
		expect(a.doc.focus).not.toHaveBeenCalled();
		expect(document.activeElement).toBe(lines()[0]);
	});

	it("row 67 r8_down_at_x: Down on the last line lands under x on the first line below", () => {
		plane([cell("a"), cell("b")]);
		const b = mountDoc("b");
		expect(mountDoc("a").say(leave("down", 40))).toBe(true);
		expect(b.doc.focus).toHaveBeenCalledWith({ x: 40, edge: "first" });
	});

	it("row 68 leave_down_into_non_prose: another class below, the core steps into it", () => {
		plane([cell("a"), cell("b", [])]);
		expect(mountDoc("a").say(leave("down"))).toBe(true);
		expect(selected()).toEqual(["b"]);
	});

	it("row 69 leave_down_into_end_line: down from the last cell, the end line", () => {
		plane([cell("a")]);
		expect(mountDoc("a").say(leave("down", 40))).toBe(true);
		expect(document.activeElement).toBe(endLine());
	});

	it("row 70 leave_down_into_line: a summoned line below is landed in first", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a");
		const b = mountDoc("b");
		plus("a");
		expect(a.say(leave("down", 40))).toBe(true);
		expect(b.doc.focus).not.toHaveBeenCalled();
		expect(document.activeElement).toBe(lines()[0]);
	});

	it("row 71 r8_left_to_end: Left at the start lands at the end above", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a");
		mountDoc("b").say(leave("left"));
		expect(a.doc.focus).toHaveBeenCalledWith("end");
	});

	it("row 72 leave_left_into_non_prose: the core steps", () => {
		plane([cell("a", []), cell("b")]);
		expect(mountDoc("b").say(leave("left"))).toBe(true);
		expect(selected()).toEqual(["a"]);
	});

	it("row 73 r8_right_to_start: Right at the end lands at the start below", () => {
		plane([cell("a"), cell("b")]);
		const b = mountDoc("b");
		mountDoc("a").say(leave("right"));
		expect(b.doc.focus).toHaveBeenCalledWith("start");
	});

	it("row 74 leave_right_into_non_prose: the core steps, or the end line under the last", () => {
		plane([cell("a"), cell("b", [])]);
		const a = mountDoc("a");
		expect(a.say(leave("right"))).toBe(true);
		expect(selected()).toEqual(["b"]);
		plane([cell("a")]);
		expect(a.say(leave("right"))).toBe(true);
		expect(document.activeElement).toBe(endLine());
	});

	it("row 193 neighbours_read_live: a cell put in between since is the one met", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a");
		const b = mountDoc("b");
		plane([cell("a"), cell("n", []), cell("b")]);
		expect(b.say(leave("up"))).toBe(true);
		expect(a.doc.focus).not.toHaveBeenCalled();
		expect(selected()).toEqual(["n"]);
	});
});

describe("E. Shift+arrows spill into cell selection", () => {
	it("rows 92-95 r10_spill_*: this cell and the next one that way, any class, anchored here", () => {
		plane([cell("a", []), cell("b"), cell("c", [])]);
		const b = mountDoc("b");
		expect(b.say(leave("up", 0, true))).toBe(true);
		expect(selected()).toEqual(["a", "b"]);
		expect(readEditor(VIEWER, "p1").anchor).toBe("b");
		expect(document.activeElement).toBe(planeRoot());
		expect(b.say(leave("down", 0, true))).toBe(true);
		expect(selected()).toEqual(["b", "c"]);
		expect(b.say(leave("left", 0, true))).toBe(true);
		expect(selected()).toEqual(["a", "b"]);
		expect(b.say(leave("right", 0, true))).toBe(true);
		expect(selected()).toEqual(["b", "c"]);
	});

	it("row 99: Shift goes on extending as cell selection from the anchor", () => {
		plane([cell("a"), cell("b"), cell("c")]);
		mountDoc("a").say(leave("down", 0, true));
		press(planeRoot(), "ArrowDown", { shiftKey: true });
		expect(selected()).toEqual(["a", "b", "c"]);
	});

	it("rows 96-97 r10_no_cell_*: no cell that way, the editor extends its own selection", () => {
		plane([cell("a"), cell("b")]);
		expect(mountDoc("a").say(leave("up", 0, true))).toBe(false);
		expect(mountDoc("b").say(leave("down", 0, true))).toBe(false);
		expect(selected()).toEqual([]);
	});

	it("row 101 spill_esc_clears: Escape clears the spill", () => {
		plane([cell("a"), cell("b")]);
		mountDoc("b").say(leave("up", 0, true));
		press(planeRoot(), "Escape");
		expect(selected()).toEqual([]);
	});
});

describe("J, K. merge and split, not built: they fall through", () => {
	it("row 154: Backspace at the start of a cell with text, prose above, does nothing yet", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", fakeDoc(false));
		expect(mountDoc("b", fakeDoc(false)).say({ kind: "erase", dir: "back" })).toBe(false);
		expect(notify).not.toHaveBeenCalled();
		expect(a.doc.append).not.toHaveBeenCalled();
	});

	it("rows 156-157 merge_not_into_*: nor into another class or the title", () => {
		plane([cell("a", []), cell("b")]);
		expect(mountDoc("a").say({ kind: "erase", dir: "back" })).toBe(false);
		expect(mountDoc("b", fakeDoc(false)).say({ kind: "erase", dir: "back" })).toBe(false);
		expect(notify).not.toHaveBeenCalled();
	});

	it("row 164: Cmd+Enter mid-text does nothing yet; row 175 no_split_classless", () => {
		plane([cell("a"), cell("b", [])]);
		const a = mountDoc("a", fakeDoc(false));
		expect(a.say({ kind: "break", at: "mid" })).toBe(false);
		expect(mountDoc("b").say({ kind: "break", at: "mid" })).toBe(false);
		expect(notify).not.toHaveBeenCalled();
		expect(a.doc.split).not.toHaveBeenCalled();
		expect(lines()).toHaveLength(1);
	});

	it("row 162 erase_forward_noop: Delete at the end does nothing", () => {
		plane([cell("a"), cell("b")]);
		expect(mountDoc("a", fakeDoc(false)).say({ kind: "erase", dir: "forward" })).toBe(false);
	});
});

describe("M. live writes", () => {
	it("row 192 focused_cell_removed: the caret goes where R2 would, the end of the one above", async () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a");
		const d = fakeDoc(false);
		focusDoc = d;
		await draw("b", "TestFocusDoc");
		focusDoc = null;
		act(() => row("b").querySelector<HTMLElement>("[data-focus-doc]")?.focus());
		plane([cell("a")]);
		expect(a.doc.focus).toHaveBeenCalledWith("end");
	});

	it("row 192, top: the title end", async () => {
		plane([cell("a")]);
		const d = fakeDoc(false);
		focusDoc = d;
		await draw("a", "TestFocusDoc");
		focusDoc = null;
		act(() => row("a").querySelector<HTMLElement>("[data-focus-doc]")?.focus());
		plane([]);
		expect(onTitle).toHaveBeenCalledWith("end");
	});

	it("row 192, not focused: a cell removed elsewhere moves no caret", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a");
		mountDoc("b");
		plane([cell("a")]);
		expect(a.doc.focus).not.toHaveBeenCalled();
		expect(onTitle).not.toHaveBeenCalled();
	});

	it("row 194 standin_written_meanwhile: written since `/`, the pick goes in after and the cell stays", () => {
		plane([cell("a"), cell("b")]);
		const d = fakeDoc(true);
		const a = mountDoc("a", d);
		a.say({ kind: "slash" });
		vi.mocked(d.doc.blank).mockReturnValue(false);
		press(lines()[0], "Enter");
		expect(ops().map(([op]) => op)).toEqual(["cell.create"]);
		expect(notify.mock.calls[0][1]).toMatchObject({ index: 1 });
		expect(row("a").hidden).toBe(false);
	});
});
