// The prose set on a real plane in jsdom, one test per interaction table row
// (task-162) the set decides, named `row N` with the table's test name. The
// markdown editors are fakes registered with the kit (../../plane.testing),
// so what is checked is what the set asks of the plane and the editors,
// not what an editor does with it: that half is the kit's browser tests.
//
// Rows the set declines are here too, where declining is the rule: the
// core's default runs, or nothing does.

import { type Cut, pathKey, register } from "@nustackdev/ui-kit";
import { act, useEffect } from "react";
import { describe, expect, it, vi } from "vitest";
import {
	cell,
	draw,
	drawReadOnly,
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
	registerEditable,
	render,
	row,
	selected,
	title,
	typeInto,
	undraw,
	VIEWER,
	WITH_DEFAULT,
} from "../../plane.testing";
import { readEditor } from "../../state";
import type { Cell } from "../../types";
import { type Sugar, sugars } from "..";
import { prose } from ".";
import { NEW_CELL_HINT, WRITE_HINT } from "./hints";
import { editorRules, inputRules, type Rule, titleRules } from "./rules";

/** A view that is a markdown editor with something to focus, as one is. */
let focusDoc: ReturnType<typeof fakeDoc> | null = null;
register("TestFocusDoc", {
	component: ({ path }: { path: string[] }) => {
		// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
		useEffect(() => (focusDoc ? registerEditable(path, focusDoc.doc) : undefined), [pathKey(path)]);
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
	const all = [...editorRules, ...inputRules, ...titleRules] as Rule<{ kind: string }, unknown>[];

	it("names its way back for every rule, and every rule it names is one", () => {
		const names = new Set(all.map((r) => r.rule));
		for (const r of all) {
			expect(r.back.trim(), r.rule).not.toBe("");
			for (const named of r.back.match(/R\d+/g) ?? []) expect(names, r.rule).toContain(named);
		}
	});

	it("is R1 to R10, merge and split, each the other's way back", () => {
		expect([...new Set(all.map((r) => r.rule))].sort()).toEqual(
			["R1", "R10", "R2", "R5", "R6", "R7", "R8", "merge", "split"].sort(),
		);
		expect(all.find((r) => r.rule === "merge")?.back).toBe("split");
		expect(all.find((r) => r.rule === "split")?.back).toBe("merge");
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

	it("row 10 r8_line_up_into_prose: Up, Left or Backspace from the line lands at the prose cell's end", () => {
		for (const key of ["ArrowUp", "ArrowLeft", "Backspace"]) {
			plane([cell("a")]);
			const a = mountDoc("a");
			press(endLine(), key);
			expect(a.doc.focus, key).toHaveBeenCalledWith("end");
			expect(selected(), key).toEqual([]);
		}
	});

	it("row 10 island_edge_line_up: another class above, or Backspace there, the caret stays in the line", () => {
		for (const key of ["ArrowUp", "ArrowLeft", "Backspace"]) {
			plane([cell("a", [])]);
			act(() => endLine().focus());
			press(endLine(), key);
			expect(selected(), key).toEqual([]);
			expect(document.activeElement, key).toBe(endLine());
		}
	});

	it("row 11 r8_line_down_into_prose: Down or Right from a summoned line lands at the start below", () => {
		for (const key of ["ArrowDown", "ArrowRight"]) {
			plane([cell("a"), cell("b")]);
			mountDoc("a");
			const b = mountDoc("b");
			plus("a");
			press(lines()[0], key);
			expect(b.doc.focus, key).toHaveBeenCalledWith("start");
			expect(selected(), key).toEqual([]);
			expect(lines(), key).toHaveLength(1);
		}
	});

	it("row 11 island_edge_line_down: another class below, the summoned line stays with the caret", () => {
		plane([cell("a"), cell("b", [])]);
		plus("a");
		press(lines()[0], "ArrowDown");
		expect(selected()).toEqual([]);
		expect(lines()).toHaveLength(2);
		expect(document.activeElement).toBe(lines()[0]);
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

	it("row 29, decision B: a line summoned at the top is landed in first", () => {
		const opener: Sugar = {
			class: "prose",
			onEditor: (_c, i, api) => {
				if (i.kind !== "slash") return false;
				api.openInput(null);
				return true;
			},
		};
		plane([cell("a"), cell("b")], { sugars: [opener, prose] });
		const a = mountDoc("a");
		mountDoc("b").say({ kind: "slash" });
		expect(lines()).toHaveLength(2);
		expect(title({ kind: "leave", dir: "down" })).toBe(true);
		expect(a.doc.focus).not.toHaveBeenCalled();
		expect(selected()).toEqual([]);
		expect(document.activeElement).toBe(lines()[0]);
	});

	it("row 30 r8_title_right_into_prose: Right at the end too", () => {
		plane([cell("a")]);
		const a = mountDoc("a");
		expect(title({ kind: "leave", dir: "right" })).toBe(true);
		expect(a.doc.focus).toHaveBeenCalledWith("start");
	});

	it("row 31 island_edge_title: another class on top, the caret stays in the title", () => {
		plane([cell("a", []), cell("b")]);
		expect(title({ kind: "leave", dir: "down" })).toBe(true);
		expect(selected()).toEqual([]);
		expect(onTitle).not.toHaveBeenCalled();
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

	it("row 52 r7_drops_trailing_empty_lines: the empty lines after the text go, a blank cell is left alone", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", fakeDoc(false));
		a.say({ kind: "break", at: "end" });
		expect(a.doc.split).toHaveBeenCalledOnce();
		expect(document.activeElement).toBe(lines()[0]);
		plane([cell("a"), cell("b")]);
		const b = mountDoc("b");
		b.say({ kind: "break", at: "end" });
		expect(b.doc.split).not.toHaveBeenCalled();
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

	it("row 65 island_edge_up: another class above, the caret stays", () => {
		plane([cell("a", []), cell("b")]);
		expect(mountDoc("b").say(leave("up", 40))).toBe(true);
		expect(selected()).toEqual([]);
	});

	it("row 65/68 island_edge_keys: past another class the key is spent, nothing selected", () => {
		for (const [key, dir] of [
			["ArrowUp", "up"],
			["ArrowDown", "down"],
		] as const) {
			plane([cell("a"), cell("b", []), cell("c"), cell("d", []), cell("e")]);
			const c = mountDoc("c");
			// As the kit's editor does: a key it answers is consumed there and
			// bubbles on, default prevented, the plane drawn anew by the time
			// it arrives (the browser runs what the intent changed in between).
			const el = row("c");
			const off = (e: Event) => {
				let took = false;
				act(() => {
					took = c.say(leave(dir));
				});
				if (took) e.preventDefault();
			};
			el.addEventListener("keydown", off);
			el.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
			el.removeEventListener("keydown", off);
			expect(selected(), key).toEqual([]);
		}
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

	it("row 68 island_edge_down: another class below, the caret stays", () => {
		plane([cell("a"), cell("b", [])]);
		expect(mountDoc("a").say(leave("down"))).toBe(true);
		expect(selected()).toEqual([]);
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

	it("row 72 island_edge_left: the caret stays", () => {
		plane([cell("a", []), cell("b")]);
		expect(mountDoc("b").say(leave("left"))).toBe(true);
		expect(selected()).toEqual([]);
	});

	it("row 73 r8_right_to_start: Right at the end lands at the start below", () => {
		plane([cell("a"), cell("b")]);
		const b = mountDoc("b");
		mountDoc("a").say(leave("right"));
		expect(b.doc.focus).toHaveBeenCalledWith("start");
	});

	it("row 74 island_edge_right: the caret stays, or the end line under the last", () => {
		plane([cell("a"), cell("b", [])]);
		const a = mountDoc("a");
		expect(a.say(leave("right"))).toBe(true);
		expect(selected()).toEqual([]);
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
		expect(selected()).toEqual([]);
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

	it("rows 92-93 r10_spill_once: the key the editor spilt with does not extend the selection again", () => {
		plane([cell("a"), cell("b"), cell("c"), cell("d")]);
		const b = mountDoc("b");
		// The kit's editor takes the key, default prevented, and it bubbles on
		// to a plane already drawn with the spill.
		const el = row("b");
		const off = (e: Event) => {
			let took = false;
			act(() => {
				took = b.say(leave("down", 0, true));
			});
			if (took) e.preventDefault();
		};
		el.addEventListener("keydown", off);
		el.dispatchEvent(
			new KeyboardEvent("keydown", {
				key: "ArrowDown",
				shiftKey: true,
				bubbles: true,
				cancelable: true,
			}),
		);
		el.removeEventListener("keydown", off);
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

/**
 * A document as paragraphs, the caret between two of them: enough of the
 * kit's commands to see text move between cells. `markdown`, `tail`,
 * `split`, `cut` and `append` keep the kit's rules: paragraphs join at a
 * blank line, a cut takes everything after the caret, append into a blank
 * one replaces it and leaves the caret at the join. A held cut (`cuts`,
 * each one handed out) shows at once; `undo` puts the document back as it
 * was when untouched since, else appends the tail; either end, once.
 */
function paper(blocks: string[], caret = 0) {
	const d = fakeDoc();
	const at = { blocks: [...blocks], caret };
	const cuts: Cut[] = [];
	const md = (bs: string[]) => bs.join("\n\n");
	const add = (text: string) => {
		const more = text ? text.split("\n\n") : [];
		at.caret = at.blocks.length;
		at.blocks = [...at.blocks, ...more];
	};
	vi.mocked(d.doc.blank).mockImplementation(() => at.blocks.length === 0);
	vi.mocked(d.doc.markdown).mockImplementation(() => md(at.blocks));
	vi.mocked(d.doc.tail).mockImplementation(() => md(at.blocks.slice(at.caret)));
	vi.mocked(d.doc.split).mockImplementation(() => {
		const tail = md(at.blocks.slice(at.caret));
		at.blocks = at.blocks.slice(0, at.caret);
		return tail;
	});
	vi.mocked(d.doc.cut).mockImplementation(() => {
		const whole = [...at.blocks];
		const tail = md(whole.slice(at.caret));
		at.blocks = whole.slice(0, at.caret);
		const head = md(at.blocks);
		let open = true;
		const c: Cut = {
			tail,
			keep: vi.fn(() => {
				open = false;
			}),
			undo: vi.fn(() => {
				if (!open) return;
				open = false;
				if (md(at.blocks) === head) at.blocks = whole;
				else add(tail);
			}),
		};
		cuts.push(c);
		return c;
	});
	vi.mocked(d.doc.append).mockImplementation(add);
	return { ...d, at, cuts };
}

/** The one held cut `p` handed out. */
function onlyCut(p: ReturnType<typeof paper>): Cut {
	expect(p.cuts).toHaveLength(1);
	return p.cuts[0] as Cut;
}

describe("J. merge", () => {
	it("row 154 merge_into_prose_above: the text goes onto the end above, saved, then this cell goes, caret at the join", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", paper(["one"]));
		const b = mountDoc("b", paper(["two"]));
		expect(b.say({ kind: "erase", dir: "back" })).toBe(true);
		expect(a.doc.append).toHaveBeenCalledWith("two");
		expect(a.at.blocks).toEqual(["one", "two"]);
		expect(a.doc.commit).toHaveBeenCalled();
		// The text was in `a` and saved before the remove was sent.
		const appended = vi.mocked(a.doc.commit).mock.invocationCallOrder[0];
		const removed = notify.mock.invocationCallOrder[0];
		expect(appended).toBeLessThan(removed);
		expect(ops()).toEqual([["cell.delete", "b"]]);
		expect(row("b").hidden).toBe(true);
		expect(a.doc.focus).toHaveBeenCalledWith("kept");
	});

	it("row 155 merge_into_blank: into a blank cell above the text replaces it", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", paper([]));
		const b = mountDoc("b", paper(["two"]));
		// Blank above is not blank here: this is merge, not R2.
		expect(b.say({ kind: "erase", dir: "back" })).toBe(true);
		expect(a.at.blocks).toEqual(["two"]);
		expect(ops()).toEqual([["cell.delete", "b"]]);
	});

	it("row 156 merge_not_into_non_prose: another class above, nothing happens", () => {
		plane([cell("a", []), cell("b")]);
		const a = mountDoc("a", paper(["one"]));
		expect(mountDoc("b", paper(["two"])).say({ kind: "erase", dir: "back" })).toBe(false);
		expect(a.doc.append).not.toHaveBeenCalled();
		expect(notify).not.toHaveBeenCalled();
	});

	it("row 157 merge_not_into_title: the top cell, nothing happens", () => {
		plane([cell("a"), cell("b")]);
		expect(mountDoc("a", paper(["one"])).say({ kind: "erase", dir: "back" })).toBe(false);
		expect(notify).not.toHaveBeenCalled();
		expect(onTitle).not.toHaveBeenCalled();
	});

	it("row 158 merge_heading: a heading arrives as the markdown it is", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", paper(["one"]));
		mountDoc("b", paper(["# Two", "three"])).say({ kind: "erase", dir: "back" });
		expect(a.doc.append).toHaveBeenCalledWith("# Two\n\nthree");
	});

	it("row 41 still wins: a blank cell is removed by R2, not merged", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", paper(["one"]));
		mountDoc("b", paper([])).say({ kind: "erase", dir: "back" });
		expect(a.doc.append).not.toHaveBeenCalled();
		expect(a.doc.focus).toHaveBeenCalledWith("end");
	});

	it("removes nothing until the joined text is in the store", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", paper(["one"]));
		const b = mountDoc("b", paper(["two"]));
		a.hold();
		b.say({ kind: "erase", dir: "back" });
		expect(a.at.blocks).toEqual(["one", "two"]);
		expect(a.doc.focus).toHaveBeenCalledWith("kept");
		expect(notify).not.toHaveBeenCalled();
		a.stored();
		expect(ops()).toEqual([["cell.delete", "b"]]);
	});

	it("hides this cell at once, in the frame the text joins above, and deletes it once stored", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", paper(["one"]));
		const b = mountDoc("b", paper(["two"]));
		a.hold();
		b.say({ kind: "erase", dir: "back" });
		expect(a.at.blocks).toEqual(["one", "two"]);
		expect(row("b").hidden).toBe(true);
		expect(notify).not.toHaveBeenCalled();
		a.stored();
		expect(ops()).toEqual([["cell.delete", "b"]]);
		expect(row("b").hidden).toBe(true);
	});

	it("brings this cell back, nothing deleted, when the cell above is lost before the join is stored", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", paper(["one"]));
		const b = mountDoc("b", paper(["two"]));
		a.hold();
		b.say({ kind: "erase", dir: "back" });
		expect(row("b").hidden).toBe(true);
		a.lose();
		expect(notify).not.toHaveBeenCalled();
		expect(row("b").hidden).toBe(false);
		expect(b.at.blocks).toEqual(["two"]);
	});

	it("never removes when the cell above did not take the text", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", paper(["one"]));
		vi.mocked(a.doc.append).mockImplementation(() => {});
		mountDoc("b", paper(["two"])).say({ kind: "erase", dir: "back" });
		expect(a.doc.commit).not.toHaveBeenCalled();
		expect(notify).not.toHaveBeenCalled();
	});

	it("leaves both when this cell is written while the join is being stored", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", paper(["one"]));
		const b = mountDoc("b", paper(["two"]));
		a.hold();
		b.say({ kind: "erase", dir: "back" });
		expect(row("b").hidden).toBe(true);
		b.at.blocks = ["two, and more"];
		a.stored();
		expect(notify).not.toHaveBeenCalled();
		expect(row("b").hidden).toBe(false);
	});

	it("declines past a summoned input line, as R8 does", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", paper(["one"]));
		const b = mountDoc("b", paper(["two"]));
		plus("a");
		expect(b.say({ kind: "erase", dir: "back" })).toBe(false);
		expect(a.doc.append).not.toHaveBeenCalled();
		expect(notify).not.toHaveBeenCalled();
	});

	it("row 162 erase_forward_noop: Delete at the end does nothing", () => {
		plane([cell("a"), cell("b")]);
		expect(mountDoc("a", paper(["one"])).say({ kind: "erase", dir: "forward" })).toBe(false);
		expect(notify).not.toHaveBeenCalled();
	});
});

describe("K. split", () => {
	/** Split `a` and ship the new cell: its id and its document, once registered. */
	function splitA(a: ReturnType<typeof paper>, into = paper([])) {
		expect(a.say({ kind: "break", at: "mid" })).toBe(true);
		const id = created()[0].cell_id as string;
		expect(created()[0]).toMatchObject({ name: "text", index: 1 });
		plane([cell("a"), cell(id), cell("z")]);
		return { id, into };
	}

	it("row 164 split_moves_tail_after_append: the tail is handed over, then cut here, caret at its start", () => {
		plane([cell("a"), cell("z")]);
		const a = mountDoc("a", paper(["one", "two"], 1));
		const { id, into } = splitA(a);
		// Shipped, no document yet: hidden rather than empty, and nothing cut.
		expect(row(id).hidden).toBe(true);
		expect(a.doc.cut).not.toHaveBeenCalled();
		mountDoc(id, into);
		expect(into.doc.append).toHaveBeenCalledWith("two");
		expect(into.doc.focus).toHaveBeenCalledWith("start");
		// The new cell holds the tail and saves it, then it is cut here.
		expect(a.doc.cut).toHaveBeenCalledOnce();
		const order = (f: unknown) => vi.mocked(f as () => void).mock.invocationCallOrder[0] as number;
		expect(order(into.doc.append)).toBeLessThan(order(into.doc.commit));
		expect(order(into.doc.commit)).toBeLessThan(order(a.doc.cut));
		expect(a.doc.split).not.toHaveBeenCalled();
		expect(a.at.blocks).toEqual(["one"]);
		expect(into.at.blocks).toEqual(["two"]);
		// Stored at once here: the cut is kept, never undone.
		const cut = onlyCut(a);
		expect(cut.tail).toBe("two");
		expect(cut.keep).toHaveBeenCalledOnce();
		expect(cut.undo).not.toHaveBeenCalled();
		expect(row(id).hidden).toBe(false);
	});

	it("row 167 split_at_start: everything goes below, this cell left blank", () => {
		plane([cell("a"), cell("z")]);
		const a = mountDoc("a", paper(["one", "two"], 0));
		const { id, into } = splitA(a);
		mountDoc(id, into);
		expect(a.at.blocks).toEqual([]);
		expect(into.at.blocks).toEqual(["one", "two"]);
		expect(onlyCut(a).keep).toHaveBeenCalledOnce();
	});

	it("row 116 split_in_list: allowed, the tail is whatever the editor cuts", () => {
		plane([cell("a"), cell("z")]);
		const a = mountDoc("a", paper(["- one", "- two"], 1));
		const { id, into } = splitA(a);
		mountDoc(id, into);
		expect(into.at.blocks).toEqual(["- two"]);
		expect(a.at.blocks).toEqual(["- one"]);
		expect(onlyCut(a).keep).toHaveBeenCalledOnce();
	});

	it("row 174 split_concurrent_write: written here meanwhile, the cut is not made and both keep the text", () => {
		plane([cell("a"), cell("z")]);
		const a = mountDoc("a", paper(["one", "two"], 1));
		const { id, into } = splitA(a);
		// Another tab writes into `a` before the new cell's document arrives.
		a.at.blocks = ["one", "two, edited"];
		mountDoc(id, into);
		expect(into.at.blocks).toEqual(["two"]);
		expect(a.doc.cut).not.toHaveBeenCalled();
		expect(a.at.blocks).toEqual(["one", "two, edited"]);
	});

	it("row 173 split_no_register_keeps_text: a cell that never takes it leaves the tail here, and shows", () => {
		plane([cell("a"), cell("z")]);
		const a = mountDoc("a", paper(["one", "two"], 1));
		const { id } = splitA(a);
		expect(row(id).hidden).toBe(true);
		plane([cell("a"), { ...cell(id), has_ui: false }, cell("z")]);
		expect(row(id).hidden).toBe(false);
		expect(readEditor(VIEWER, "p1").requests).toEqual([]);
		expect(a.doc.cut).not.toHaveBeenCalled();
		expect(a.at.blocks).toEqual(["one", "two"]);
	});

	it("cuts nothing until the new cell's text is in the store", () => {
		plane([cell("a"), cell("z")]);
		const a = mountDoc("a", paper(["one", "two"], 1));
		const into = paper([]);
		into.hold();
		const { id } = splitA(a, into);
		mountDoc(id, into);
		expect(into.at.blocks).toEqual(["two"]);
		expect(into.doc.commit).toHaveBeenCalled();
		// On screen the tail left in the same frame; in the store it is still
		// here, the cut held, neither kept nor undone.
		expect(a.at.blocks).toEqual(["one"]);
		const cut = onlyCut(a);
		expect(cut.keep).not.toHaveBeenCalled();
		expect(cut.undo).not.toHaveBeenCalled();
		into.stored();
		expect(cut.keep).toHaveBeenCalledOnce();
		expect(cut.undo).not.toHaveBeenCalled();
		expect(a.at.blocks).toEqual(["one"]);
	});

	it("undoes the cut when the new cell is lost before its text is stored", () => {
		plane([cell("a"), cell("z")]);
		const a = mountDoc("a", paper(["one", "two"], 1));
		const into = paper([]);
		into.hold();
		const { id } = splitA(a, into);
		mountDoc(id, into);
		expect(a.at.blocks).toEqual(["one"]);
		into.lose();
		const cut = onlyCut(a);
		expect(cut.undo).toHaveBeenCalledOnce();
		expect(cut.keep).not.toHaveBeenCalled();
		expect(a.at.blocks).toEqual(["one", "two"]);
	});

	it("never cuts when the new cell did not take the tail", () => {
		plane([cell("a"), cell("z")]);
		const a = mountDoc("a", paper(["one", "two"], 1));
		const into = paper([]);
		vi.mocked(into.doc.append).mockImplementation(() => {});
		const { id } = splitA(a, into);
		mountDoc(id, into);
		expect(into.doc.saved).not.toHaveBeenCalled();
		expect(a.doc.cut).not.toHaveBeenCalled();
		expect(a.at.blocks).toEqual(["one", "two"]);
	});

	it("keeps what this cell is written while the tail is being stored", () => {
		plane([cell("a"), cell("z")]);
		const a = mountDoc("a", paper(["one", "two"], 1));
		const into = paper([]);
		into.hold();
		const { id } = splitA(a, into);
		mountDoc(id, into);
		// Typed into the head while the cut is held: the keep saves it along.
		a.at.blocks = ["one, edited"];
		into.stored();
		expect(onlyCut(a).keep).toHaveBeenCalledOnce();
		expect(onlyCut(a).undo).not.toHaveBeenCalled();
		expect(a.at.blocks).toEqual(["one, edited"]);
		expect(into.at.blocks).toEqual(["two"]);
	});

	it("row 168: at the end it is R7, never a split", () => {
		plane([cell("a"), cell("z")]);
		const a = mountDoc("a", paper(["one"], 1));
		a.say({ kind: "break", at: "end" });
		expect(created()).toEqual([]);
		expect(lines()).toHaveLength(2);
	});

	it("row 175 no_split_classless: a classless cell's document, nothing", () => {
		plane([cell("a", []), cell("z")]);
		expect(mountDoc("a", paper(["one", "two"], 1)).say({ kind: "break", at: "mid" })).toBe(false);
		expect(notify).not.toHaveBeenCalled();
	});

	it("rows 164 + 154: split, then merge back, is the original markdown", () => {
		plane([cell("a"), cell("z")]);
		const a = mountDoc("a", paper(["one", "two"], 1));
		const before = a.doc.markdown();
		const { id, into } = splitA(a);
		const b = mountDoc(id, into);
		expect(a.doc.markdown()).toBe("one");
		expect(onlyCut(a).keep).toHaveBeenCalledOnce();
		// The caret is at the new cell's start: Backspace there merges.
		expect(b.say({ kind: "erase", dir: "back" })).toBe(true);
		expect(a.doc.markdown()).toBe(before);
		expect(ops().at(-1)).toEqual(["cell.delete", id]);
	});
});

describe("a document opened in two frames: read-only first, editing later", () => {
	it("split lands once the new cell's document opens", async () => {
		plane([cell("a"), cell("z")]);
		const a = mountDoc("a", paper(["one", "two"], 1));
		a.say({ kind: "break", at: "mid" });
		const id = created()[0].cell_id as string;
		plane([cell("a"), cell(id), cell("z")]);
		await drawReadOnly(id);
		// Drawn, read-only: the request waits, nothing cut, and the cell stays
		// out of sight, the tail still in sight in the cell it is cut from.
		expect(row(id).hidden).toBe(true);
		expect(readEditor(VIEWER, "p1").requests).toHaveLength(1);
		expect(a.doc.cut).not.toHaveBeenCalled();
		expect(a.at.blocks).toEqual(["one", "two"]);
		const into = mountDoc(id, paper([]));
		expect(into.at.blocks).toEqual(["two"]);
		expect(into.doc.focus).toHaveBeenCalledWith("start");
		expect(a.at.blocks).toEqual(["one"]);
		expect(onlyCut(a).keep).toHaveBeenCalledOnce();
		expect(row(id).hidden).toBe(false);
	});

	it("R1's text lands once the new cell's document opens", async () => {
		plane([]);
		act(() => endLine().focus());
		typeInto(endLine(), "hi");
		const id = created()[0].cell_id as string;
		plane([cell(id)]);
		await drawReadOnly(id);
		expect(readEditor(VIEWER, "p1").requests).toHaveLength(1);
		expect(endLine().value).toBe("hi");
		const d = mountDoc(id);
		expect(d.doc.focus).toHaveBeenCalledWith("end");
		expect(d.doc.type).toHaveBeenCalledExactlyOnceWith("hi");
		expect(endLine().value).toBe("");
	});

	it("a create that asks for the caret gets it once the document opens (R5)", async () => {
		plane([cell("a")]);
		title({ kind: "enter", end: true });
		const id = created()[0].cell_id as string;
		plane([cell(id), cell("a")]);
		await drawReadOnly(id);
		const d = mountDoc(id);
		expect(d.doc.focus).toHaveBeenCalledWith("start");
	});

	it("a document that goes without ever opening lets the request go, the text back in the line", async () => {
		plane([]);
		act(() => endLine().focus());
		typeInto(endLine(), "hi");
		const id = created()[0].cell_id as string;
		plane([cell(id)]);
		await drawReadOnly(id);
		undraw(id);
		expect(readEditor(VIEWER, "p1").requests).toEqual([]);
		expect(endLine().value).toBe("hi");
		expect(row(id).hidden).toBe(false);
	});
});

describe("the receiver written while the move is being stored", () => {
	it("merge leaves both when the cell above no longer holds the text", () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a", paper(["one"]));
		const b = mountDoc("b", paper(["two"]));
		a.hold();
		b.say({ kind: "erase", dir: "back" });
		expect(row("b").hidden).toBe(true);
		a.at.blocks = ["one"];
		a.stored();
		expect(notify).not.toHaveBeenCalled();
		expect(row("b").hidden).toBe(false);
	});

	it("split leaves both when the new cell no longer holds the tail", () => {
		plane([cell("a"), cell("z")]);
		const a = mountDoc("a", paper(["one", "two"], 1));
		a.say({ kind: "break", at: "mid" });
		const id = created()[0].cell_id as string;
		plane([cell("a"), cell(id), cell("z")]);
		const into = paper([]);
		into.hold();
		mountDoc(id, into);
		// Cut at once, then the new cell rewritten before its read came back.
		expect(a.at.blocks).toEqual(["one"]);
		into.at.blocks = ["something else"];
		into.stored();
		const cut = onlyCut(a);
		expect(cut.undo).toHaveBeenCalledOnce();
		expect(cut.keep).not.toHaveBeenCalled();
		// Untouched here since the cut: back exactly as it was.
		expect(a.at.blocks).toEqual(["one", "two"]);
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

	it("row 192, Chrome's order: a blur to nowhere before the cell goes still lands the caret", async () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a");
		focusDoc = fakeDoc(false);
		await draw("b", "TestFocusDoc");
		focusDoc = null;
		const drawn = row("b").querySelector<HTMLElement>("[data-focus-doc]") as HTMLElement;
		act(() => drawn.focus());
		act(() => {
			drawn.dispatchEvent(new FocusEvent("focusout", { bubbles: true, relatedTarget: null }));
			drawn.blur();
		});
		plane([cell("a")]);
		expect(a.doc.focus).toHaveBeenCalledWith("end");
	});

	it("row 192, focus elsewhere in the plane meanwhile: the caret stays there", async () => {
		plane([cell("a"), cell("b")]);
		const a = mountDoc("a");
		focusDoc = fakeDoc(false);
		await draw("b", "TestFocusDoc");
		focusDoc = null;
		const drawn = row("b").querySelector<HTMLElement>("[data-focus-doc]") as HTMLElement;
		act(() => drawn.focus());
		act(() => {
			drawn.dispatchEvent(new FocusEvent("focusout", { bubbles: true, relatedTarget: null }));
		});
		act(() => endLine().focus());
		plane([cell("a")]);
		expect(a.doc.focus).not.toHaveBeenCalled();
		expect(document.activeElement).toBe(endLine());
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
