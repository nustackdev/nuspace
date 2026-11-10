// The core plane with no sugar, rendered in jsdom: what the interaction table
// (task-162) marks `core`, and the machinery every sugar acts through. The
// input line opens the menu, cells are created, selected, moved and deleted
// through the one remove path, the title's intents get the core defaults,
// and a focus request waits for its cell's document and is consumed when
// that registers. Then routing: a fake sugar claiming and declining.
//
// Every plane here is handed an empty sugar list, while the registry names
// the prose set (./sugar): this file is the core with the sugar layer
// removed, and it passing is what says the core works without it.
//
// The markdown editors are the shared harness's fakes (./plane.testing.tsx).

import { type MarkdownHandle, type MarkdownIntent, pathKey, register } from "@nustackdev/ui-kit";
import { act, useEffect } from "react";
import { describe, expect, it, vi } from "vitest";
import type { PlaneApi } from "./api";
import {
	cell,
	draw,
	endLine,
	fakeDoc,
	handle,
	leaves,
	lines,
	menu,
	mountDoc,
	notify,
	onTitle,
	ops,
	planeRoot,
	press,
	registerEditable,
	render,
	root,
	row,
	selected,
	title,
	typeInto,
	VIEWER,
	WITH_DEFAULT,
} from "./plane.testing";
import { readEditor } from "./state";
import { sugars as SUGARS, type Sugar } from "./sugar";

/** A program's view that is no markdown editor: drawn, never registered. */
register("TestPlain", { component: () => <div /> });
/** A view that is a markdown editor: it registers `drawnDoc` at its own path on mount, as a MarkdownRef does. */
let drawnDoc: MarkdownHandle | null = null;
register("TestDoc", {
	component: ({ path }: { path: string[] }) => {
		// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value, as a MarkdownRef's.
		useEffect(() => (drawnDoc ? registerEditable(path, drawnDoc) : undefined), [pathKey(path)]);
		return <div />;
	},
});

/** A sugar that only listens: it records what it is offered and claims nothing. */
function spy(cls = "prose", claim = false) {
	const seen: { on: string; args: unknown[] }[] = [];
	let api: PlaneApi | null = null;
	const sugar: Sugar = {
		class: cls,
		onEditor: (c, i, a) => {
			api = a;
			seen.push({ on: "document", args: [c, i] });
			return claim;
		},
		onInput: (after, i, a) => {
			api = a;
			seen.push({ on: "input", args: [after, i] });
			return claim;
		},
		onTitle: (i, a) => {
			api = a;
			seen.push({ on: "title", args: [i] });
			return claim;
		},
	};
	return { sugar, seen, api: () => api as PlaneApi | null };
}

describe("the sugar layer removed", () => {
	it("is what every test here runs: the registry has sets, these planes get none", () => {
		expect(SUGARS.length).toBeGreaterThan(0);
		render([cell("a")], { specs: WITH_DEFAULT });
		// With a prose default installed and no set, typing searches.
		typeInto(endLine(), "h");
		expect(notify).not.toHaveBeenCalled();
		expect(menu()).not.toBeNull();
	});
});

describe("the input line, with no sugar", () => {
	it("opens the menu with a typed character as its query (input_char_searches_without_default)", () => {
		render([]);
		typeInto(endLine(), "h");
		expect(notify).not.toHaveBeenCalled();
		expect(endLine().value).toBe("h");
		expect(endLine().placeholder).toBe("Type to search");
		expect(menu()).not.toBeNull();
	});

	it("does nothing on Enter (input_enter_noop_without_default)", () => {
		render([], { specs: WITH_DEFAULT });
		press(endLine(), "Enter");
		expect(notify).not.toHaveBeenCalled();
		expect(menu()).toBeNull();
	});

	it("opens the menu on `/`, which is consumed (input_slash_opens_menu)", () => {
		render([]);
		press(endLine(), "/");
		expect(menu()).not.toBeNull();
		expect(endLine().value).toBe("");
	});

	it("says what it does (input_hint_by_default)", () => {
		render([], { specs: WITH_DEFAULT });
		expect(endLine().placeholder).toBe("Press / for cells");
	});

	it("filters on typing with the menu open, Escape closes it, Backspace on empty too (menu_*)", () => {
		render([]);
		press(endLine(), "/");
		typeInto(endLine(), "pro");
		expect(endLine().value).toBe("pro");
		press(endLine(), "Escape");
		expect(menu()).toBeNull();
		press(endLine(), "/");
		press(endLine(), "Backspace");
		expect(menu()).toBeNull();
		expect(lines()).toHaveLength(1);
	});

	it("creates the pick after the line's cell (menu_pick_creates_after)", () => {
		render([cell("a"), cell("b")]);
		press(endLine(), "/");
		press(endLine(), "Enter");
		expect(notify).toHaveBeenCalledWith(
			"cell.create",
			expect.objectContaining({ plane_id: "p1", name: "", after: "b" }),
		);
		expect(menu()).toBeNull();
	});

	it("goes up into the cell above, selected, and into the title from an empty plane", () => {
		render([cell("a", []), cell("b", [])]);
		press(endLine(), "ArrowUp");
		expect(selected()).toEqual(["b"]);
		expect(document.activeElement).toBe(planeRoot());
		render([]);
		press(endLine(), "ArrowUp");
		expect(onTitle).toHaveBeenCalledWith("end");
	});

	it("does nothing going down from the end line (end_line_down_noop)", () => {
		render([cell("a")]);
		act(() => endLine().focus());
		press(endLine(), "ArrowDown");
		expect(selected()).toEqual([]);
		expect(document.activeElement).toBe(endLine());
	});

	it("selects the last cell on Escape, or gives the plane the keyboard (end_line_esc_*)", () => {
		render([cell("a"), cell("b")]);
		press(endLine(), "Escape");
		expect(selected()).toEqual(["b"]);
		expect(lines()).toHaveLength(1);
		render([]);
		press(endLine(), "Escape");
		expect(document.activeElement).toBe(planeRoot());
	});

	it("summons a line with the gutter `+`, which Escape and blur take away (plus_esc_selects_cell)", () => {
		render([cell("a"), cell("b")]);
		const plus = row("a").querySelector<HTMLButtonElement>("button[aria-label='Add a line below']");
		act(() => plus?.click());
		expect(lines()).toHaveLength(2);
		expect(document.activeElement).toBe(lines()[0]);
		press(lines()[0], "Escape");
		expect(lines()).toHaveLength(1);
		expect(selected()).toEqual(["a"]);

		act(() => plus?.click());
		expect(lines()).toHaveLength(2);
		act(() => lines()[0].blur());
		expect(lines()).toHaveLength(1);
	});

	it("goes down from a summoned line into the cell below (input_leave_down)", () => {
		render([cell("a", []), cell("b", [])]);
		act(() =>
			row("a").querySelector<HTMLButtonElement>("button[aria-label='Add a line below']")?.click(),
		);
		press(lines()[0], "ArrowDown");
		expect(selected()).toEqual(["b"]);
		expect(lines()).toHaveLength(1);
	});

	it("draws no lines on a read-only plane (read_only_no_sugar)", () => {
		render([cell("a")], { editable: false });
		expect(lines()).toHaveLength(0);
	});
});

describe("opening a plane", () => {
	it("puts the caret in the end line of an empty plane in the focused pane (open_empty_focuses_line)", () => {
		render([], { focused: true });
		expect(document.activeElement).toBe(endLine());
	});

	it("leaves the keyboard alone on a plane with cells (open_cells_keep_focus)", () => {
		render([cell("a")], { focused: true });
		expect(document.activeElement).toBe(document.body);
	});

	it("leaves it alone in a pane that is not the focused one (open_unfocused_keeps_focus)", () => {
		render([]);
		expect(document.activeElement).toBe(document.body);
	});

	it("leaves it with a field being typed in (open_typing_keeps_focus)", () => {
		const field = document.createElement("input");
		document.body.append(field);
		field.focus();
		render([], { focused: true });
		expect(document.activeElement).toBe(field);
		field.remove();
	});

	it("leaves it with a dialog open, not one on its way out (open_dialog_keeps_focus)", () => {
		const dialog = document.createElement("div");
		dialog.setAttribute("role", "dialog");
		dialog.dataset.state = "open";
		document.body.append(dialog);
		render([], { focused: true });
		expect(document.activeElement).toBe(document.body);
		dialog.remove();
	});

	it("takes it from a field in a closing dialog (open_closing_dialog_yields)", () => {
		const dialog = document.createElement("div");
		dialog.setAttribute("role", "dialog");
		dialog.dataset.state = "closed";
		const field = document.createElement("input");
		dialog.append(field);
		document.body.append(dialog);
		field.focus();
		render([], { focused: true });
		expect(document.activeElement).toBe(endLine());
		dialog.remove();
	});
});

describe("the title's intents, core defaults", () => {
	it("Enter at the end goes into the cells: the top one selected (title_enter_core_at_end)", () => {
		render([cell("a", []), cell("b", [])]);
		expect(title({ kind: "enter", end: true })).toBe(true);
		expect(selected()).toEqual(["a"]);
	});

	it("Enter mid-title is the title's own (title_enter_core_blurs)", () => {
		render([cell("a")]);
		expect(title({ kind: "enter", end: false })).toBe(false);
		expect(selected()).toEqual([]);
	});

	it("leaving lands on the top cell, or the end line on an empty plane (title_leave_*)", () => {
		render([cell("a", [])]);
		expect(title({ kind: "leave", dir: "right" })).toBe(true);
		expect(selected()).toEqual(["a"]);
		render([]);
		expect(title({ kind: "leave", dir: "down" })).toBe(true);
		expect(document.activeElement).toBe(endLine());
	});

	it("stays the title's on a read-only plane (title_read_only_stays)", () => {
		render([cell("a")], { editable: false });
		expect(title({ kind: "leave", dir: "down" })).toBe(false);
		expect(title({ kind: "enter", end: true })).toBe(false);
	});
});

describe("a document's intents, core defaults", () => {
	it("a leave steps to the neighbour, anything else is the editor's (no_sugar_for_classless_doc)", () => {
		render([cell("a", []), cell("b", [])]);
		const b = mountDoc("b");
		expect(b.say({ kind: "erase", dir: "back" })).toBe(false);
		expect(b.say({ kind: "slash" })).toBe(false);
		expect(b.say({ kind: "break", at: "end" })).toBe(false);
		expect(b.say({ kind: "leave", dir: "up", extend: true, x: 0 })).toBe(false);
		expect(notify).not.toHaveBeenCalled();
		// Up out of b: a is selected, as today's step does (leave_up_into_non_prose).
		expect(b.say({ kind: "leave", dir: "up", extend: false, x: 10 })).toBe(true);
		expect(selected()).toEqual(["a"]);
	});

	it("leaving the last cell down lands in the end line; the top one up has nowhere to go", () => {
		render([cell("a"), cell("b")]);
		const a = mountDoc("a");
		const b = mountDoc("b");
		expect(b.say({ kind: "leave", dir: "right", extend: false, x: 0 })).toBe(true);
		expect(document.activeElement).toBe(endLine());
		expect(a.say({ kind: "leave", dir: "left", extend: false, x: 0 })).toBe(false);
	});

	it("routes nothing on a read-only plane", () => {
		render([cell("a"), cell("b")], { editable: false });
		const b = mountDoc("b");
		expect(b.say({ kind: "leave", dir: "up", extend: false, x: 0 })).toBe(false);
	});

	it("stops hearing a document once it leaves, and hears the next one", () => {
		render([cell("a"), cell("b")]);
		const first = mountDoc("b");
		expect(first.listeners.size).toBe(1);
		act(() => leaves.pop()?.());
		expect(first.listeners.size).toBe(0);
		const second = mountDoc("b");
		expect(second.listeners.size).toBe(1);
	});
});

describe("cell selection", () => {
	it("walks, extends and reorders from the keyboard", () => {
		render([cell("a", []), cell("b", []), cell("c", [])]);
		title({ kind: "enter", end: true });
		const plane = planeRoot();
		press(plane, "ArrowDown");
		expect(selected()).toEqual(["b"]);
		press(plane, "ArrowDown", { shiftKey: true });
		expect(selected()).toEqual(["b", "c"]);
		press(plane, "ArrowUp", { metaKey: true });
		// [b, c] up past a: each cell out of place moved after the one before it.
		expect(ops().slice(-2)).toEqual([
			["cell.move", "b"],
			["cell.move", "c"],
		]);
		expect(notify.mock.calls.at(-2)?.[1]).toEqual({ cell_id: "b", before: "a" });
		expect(notify.mock.calls.at(-1)?.[1]).toEqual({ cell_id: "c", after: "b" });
		press(plane, "Escape");
		expect(selected()).toEqual([]);
	});

	it("deletes through the one remove path: hidden at once, the cell above selected (remove_selected_one_path)", () => {
		render([cell("a", []), cell("b", []), cell("c", [])]);
		title({ kind: "enter", end: true });
		const plane = planeRoot();
		press(plane, "ArrowDown");
		press(plane, "ArrowDown", { shiftKey: true });
		press(plane, "Backspace");
		expect(ops()).toEqual([
			["cell.delete", "b"],
			["cell.delete", "c"],
		]);
		expect(row("b").hidden).toBe(true);
		expect(row("c").hidden).toBe(true);
		expect(selected()).toEqual(["a"]);
		// The server drops them: gone.
		render([cell("a", [])]);
		expect(row("b")).toBeNull();
	});

	it("Enter on a selected cell with a document focuses its end (enter_selected_prose)", () => {
		render([cell("a")]);
		const a = mountDoc("a");
		title({ kind: "enter", end: true });
		press(planeRoot(), "Enter");
		expect(a.doc.focus).toHaveBeenCalledWith("end");
		expect(selected()).toEqual([]);
	});
});

describe("focus requests", () => {
	it("a code cell's source takes the request once it has a view", async () => {
		render([]);
		press(endLine(), "/");
		press(endLine(), "Enter");
		const [, args] = notify.mock.calls[0];
		expect(args).toMatchObject({ name: "" });
		const id = args.cell_id as string;
		await act(async () => render([cell(id, [])]));
		const content = row(id).querySelector<HTMLElement>(".cm-content");
		expect(content).not.toBeNull();
		expect(row(id).contains(document.activeElement)).toBe(true);
	});

	it("a cell from a spec is landed on selected, and its document takes the caret when it registers", () => {
		render([cell("a")]);
		press(endLine(), "/");
		typeInto(endLine(), "text");
		press(endLine(), "Enter");
		const id = notify.mock.calls[0][1].cell_id as string;
		render([cell("a"), cell(id)]);
		expect(selected()).toEqual([id]);
		const doc = mountDoc(id);
		expect(doc.doc.focus).toHaveBeenCalledWith("end");
		expect(selected()).toEqual([]);
	});

	it("settles once the person goes elsewhere: a later register does not pull the caret", () => {
		render([cell("a", [])]);
		press(endLine(), "/");
		typeInto(endLine(), "text");
		press(endLine(), "Enter");
		const id = notify.mock.calls[0][1].cell_id as string;
		render([cell("a", []), cell(id)]);
		press(planeRoot(), "ArrowUp");
		expect(selected()).toEqual(["a"]);
		const doc = mountDoc(id);
		expect(doc.doc.focus).not.toHaveBeenCalled();
	});
});

describe("routing to a sugar", () => {
	it("offers a document intent to the set bound to the cell's class, and its claim stops the core", () => {
		const claim = spy("prose", true);
		render([cell("a"), cell("b")], { sugars: [claim.sugar] });
		const b = mountDoc("b");
		const i: MarkdownIntent = { kind: "leave", dir: "up", extend: false, x: 4 };
		expect(b.say(i)).toBe(true);
		expect(claim.seen).toEqual([{ on: "document", args: ["b", i] }]);
		expect(selected()).toEqual([]);
	});

	it("falls back to the core default when the set declines", () => {
		const decline = spy("prose", false);
		render([cell("a", []), cell("b")], { sugars: [decline.sugar] });
		const b = mountDoc("b");
		expect(b.say({ kind: "leave", dir: "up", extend: false, x: 0 })).toBe(true);
		expect(decline.seen).toHaveLength(1);
		expect(selected()).toEqual(["a"]);
	});

	it("never offers a classless cell's document to it", () => {
		const s = spy("prose", true);
		render([cell("a", []), cell("b", [])], { sugars: [s.sugar] });
		mountDoc("b").say({ kind: "erase", dir: "back" });
		expect(s.seen).toEqual([]);
	});

	it("offers the input line and the title only with a default spec for its class installed", () => {
		const s = spy("prose", false);
		render([cell("a")], { sugars: [s.sugar] });
		press(endLine(), "Enter");
		title({ kind: "enter", end: false });
		expect(s.seen).toEqual([]);
		render([cell("a")], { sugars: [s.sugar], specs: WITH_DEFAULT });
		press(endLine(), "Enter");
		title({ kind: "enter", end: false });
		expect(s.seen.map((x) => x.on)).toEqual(["input", "title"]);
		expect(s.api()?.defaultSpec("prose")).toBe("text");
		expect(s.api()?.defaultSpec("other")).toBeNull();
	});

	it("draws the set's hint on the input line while it has it", () => {
		const s = { ...spy().sugar, inputHint: "Write, or press / for cells" };
		render([], { sugars: [s] });
		expect(endLine().placeholder).toBe("Press / for cells");
		render([], { sugars: [s], specs: WITH_DEFAULT });
		expect(endLine().placeholder).toBe("Write, or press / for cells");
	});
});

describe("the plane api, from a sugar", () => {
	/** A sugar that runs `act` on its first document intent, with the api. */
	function on(run: (cell: string, api: PlaneApi) => void): Sugar {
		return {
			class: "prose",
			onEditor: (c, _i, api) => {
				run(c, api);
				return true;
			},
		};
	}
	const poke = (d: ReturnType<typeof fakeDoc>) => d.say({ kind: "erase", dir: "back" });

	it("remove with a focus target: the cell goes, the caret goes there (r2-shaped)", () => {
		render([cell("a"), cell("b")], {
			sugars: [on((c, api) => api.remove([c], { cell: "a", at: "end" }))],
		});
		const a = mountDoc("a");
		poke(mountDoc("b"));
		expect(ops()).toEqual([["cell.delete", "b"]]);
		expect(row("b").hidden).toBe(true);
		expect(a.doc.focus).toHaveBeenCalledWith("end");
	});

	it("remove to the title, or to the plane where there is none (r2_top_*)", () => {
		const sugar = on((c, api) => api.remove([c], { title: "end" }));
		render([cell("a")], { sugars: [sugar] });
		poke(mountDoc("a"));
		expect(onTitle).toHaveBeenCalledWith("end");
		render([cell("b")], { sugars: [sugar], title: false });
		poke(mountDoc("b"));
		expect(document.activeElement).toBe(planeRoot());
	});

	it("withdraw: out of sight now, the delete only on remove; restore brings it back; either, once", () => {
		const outs: ReturnType<PlaneApi["withdraw"]>[] = [];
		render([cell("a"), cell("b"), cell("c")], {
			sugars: [on((c, api) => outs.push(api.withdraw([c])))],
		});
		const a = mountDoc("a");
		poke(mountDoc("b"));
		poke(mountDoc("c"));
		const [b, c] = outs as [(typeof outs)[0], (typeof outs)[0]];
		// Hidden at once, nothing sent, focus left alone.
		expect(row("b").hidden).toBe(true);
		expect(row("c").hidden).toBe(true);
		expect(notify).not.toHaveBeenCalled();
		expect(a.doc.focus).not.toHaveBeenCalled();
		act(() => b.remove());
		expect(ops()).toEqual([["cell.delete", "b"]]);
		expect(row("b").hidden).toBe(true);
		act(() => c.restore());
		expect(row("c").hidden).toBe(false);
		// Each ended once: a second call either way does nothing.
		act(() => {
			b.remove();
			b.restore();
			c.remove();
			c.restore();
		});
		expect(ops()).toEqual([["cell.delete", "b"]]);
		expect(row("b").hidden).toBe(true);
		expect(row("c").hidden).toBe(false);
	});

	it("a focus request waits for the document, then is consumed and cleared (focus_request_waits_for_register)", () => {
		render([cell("a"), cell("b")], {
			sugars: [on((_c, api) => api.focus({ cell: "b", at: { x: 40, edge: "first" } }))],
		});
		poke(mountDoc("a"));
		const b = mountDoc("b");
		expect(b.doc.focus).toHaveBeenCalledExactlyOnceWith({ x: 40, edge: "first" });
		// Consumed means cleared: a second registration takes nothing.
		act(() => leaves.pop()?.());
		const again = mountDoc("b");
		expect(again.doc.focus).not.toHaveBeenCalled();
	});

	it("create with markdown and a hook: appended, focused, and the caller hears the document (split-shaped)", () => {
		const then = vi.fn();
		let made = "";
		render([cell("a"), cell("z")], {
			sugars: [
				on((c, api) => {
					made = api.create({ after: c }, "text", { at: "start", markdown: "tail", landed: then });
				}),
			],
		});
		poke(mountDoc("a"));
		expect(notify).toHaveBeenCalledWith(
			"cell.create",
			expect.objectContaining({ cell_id: made, after: "a" }),
		);
		// A set_plane without the new cell yet must not drop its request.
		render([cell("a"), cell("z")], { sugars: [] });
		render([cell("a"), cell(made), cell("z")], { sugars: [] });
		const d = mountDoc(made);
		expect(d.doc.append).toHaveBeenCalledWith("tail");
		expect(d.doc.focus).toHaveBeenCalledWith("start");
		expect(then).toHaveBeenCalledExactlyOnceWith(d.doc);
	});

	it("openInput with a home: Escape there sends the caret back, kept (r7_esc_returns_caret)", () => {
		render([cell("a"), cell("b")], {
			sugars: [on((c, api) => api.openInput(c, { cell: c, at: "kept" }))],
		});
		const a = mountDoc("a");
		a.say({ kind: "break", at: "end" });
		expect(lines()).toHaveLength(2);
		expect(document.activeElement).toBe(lines()[0]);
		press(lines()[0], "Escape");
		expect(lines()).toHaveLength(1);
		expect(a.doc.focus).toHaveBeenCalledWith("kept");
	});

	it("standIn: the menu in the cell's place; Escape brings it back, a pick replaces it (r6_*)", () => {
		render([cell("a"), cell("b")], { sugars: [on((c, api) => api.standIn(c))] });
		const a = mountDoc("a");
		a.say({ kind: "slash" });
		expect(row("a").hidden).toBe(true);
		expect(menu()).not.toBeNull();
		press(lines()[0], "Escape");
		expect(row("a").hidden).toBe(false);
		expect(a.doc.focus).toHaveBeenCalledWith("start");

		a.say({ kind: "slash" });
		press(lines()[0], "Enter");
		expect(ops().map(([op]) => op)).toEqual(["cell.create", "cell.delete"]);
		expect(notify.mock.calls[0][1]).toMatchObject({ after: "a" });
		expect(notify.mock.calls[1][1]).toEqual({ cell_id: "a" });
		expect(row("a").hidden).toBe(true);
	});

	it("select with an anchor, then the plane's Shift extends from it (r10-shaped)", () => {
		render([cell("a"), cell("b"), cell("c")], {
			sugars: [on((c, api) => api.select([c, "c"], c))],
		});
		mountDoc("b").say({ kind: "leave", dir: "down", extend: true, x: 0 });
		expect(selected()).toEqual(["b", "c"]);
		expect(document.activeElement).toBe(planeRoot());
		press(planeRoot(), "Backspace");
		expect(ops()).toEqual([
			["cell.delete", "b"],
			["cell.delete", "c"],
		]);
	});
});

describe("a create fed by the input line", () => {
	/** R1's shape: typing or Enter on the line creates from the default spec. */
	const write: Sugar = {
		class: "prose",
		onInput: (after, i, api) => {
			const spec = api.defaultSpec("prose");
			if (!spec) return false;
			api.create({ after }, spec, { at: "end", text: i.kind === "text" ? i.text : "" });
			return true;
		},
	};

	it("keeps the keys typed meanwhile in the line, then the document takes them all (r1_keys_while_pending_go_along)", () => {
		render([], { sugars: [write], specs: WITH_DEFAULT });
		act(() => endLine().focus());
		typeInto(endLine(), "h");
		const [op, args] = notify.mock.calls[0];
		expect(op).toBe("cell.create");
		expect(args).toMatchObject({ name: "text" });
		expect(args).not.toHaveProperty("before");
		expect(endLine().value).toBe("h");
		expect(menu()).toBeNull();
		typeInto(endLine(), "hello");
		// Enter is a new line in what the cell will take: the line shows the one being typed.
		press(endLine(), "Enter");
		expect(endLine().value).toBe("");
		typeInto(endLine(), "w");

		const id = args.cell_id as string;
		render([cell(id)], { sugars: [write], specs: WITH_DEFAULT });
		// The line stands in for it until its document has the text.
		expect(row(id).hidden).toBe(true);
		const d = mountDoc(id);
		expect(d.doc.focus).toHaveBeenCalledWith("end");
		expect(d.doc.type).toHaveBeenCalledExactlyOnceWith("hello\nw");
		expect(row(id).hidden).toBe(false);
		expect(endLine().value).toBe("");
		expect(notify).toHaveBeenCalledTimes(1);
	});

	it("filters with the menu open, never creates (menu_typing_filters)", () => {
		render([], { sugars: [write], specs: WITH_DEFAULT });
		press(endLine(), "/");
		typeInto(endLine(), "te");
		expect(notify).not.toHaveBeenCalled();
		expect(endLine().value).toBe("te");
	});

	it("lands the text without the caret when the person went elsewhere (r1_text_lands_caret_stays_away)", () => {
		render([], { sugars: [write], specs: WITH_DEFAULT });
		act(() => endLine().focus());
		typeInto(endLine(), "hi");
		act(() => endLine().blur());
		const id = notify.mock.calls[0][1].cell_id as string;
		render([cell(id)], { sugars: [write], specs: WITH_DEFAULT });
		const d = mountDoc(id);
		expect(d.doc.type).toHaveBeenCalledWith("hi");
		expect(d.doc.focus).not.toHaveBeenCalled();
	});

	it("gives the text back to the line when the program dies (r1_no_register_keeps_text)", () => {
		render([], { sugars: [write], specs: WITH_DEFAULT });
		act(() => endLine().focus());
		typeInto(endLine(), "hi");
		const id = notify.mock.calls[0][1].cell_id as string;
		render([cell(id, ["prose"], "boom")], { sugars: [write], specs: WITH_DEFAULT });
		// Its error shows; the line holds the text again, plain, no longer pending.
		expect(row(id).hidden).toBe(false);
		expect(readEditor(VIEWER, "p1").requests).toEqual([]);
		expect(endLine().value).toBe("hi");
		press(endLine(), "Escape");
		expect(endLine().value).toBe("");
		const d = mountDoc(id);
		expect(d.doc.type).not.toHaveBeenCalled();
	});

	it("gives the text back when the cell ships saying it draws nothing", () => {
		render([], { sugars: [write], specs: WITH_DEFAULT });
		act(() => endLine().focus());
		typeInto(endLine(), "hi");
		const id = notify.mock.calls[0][1].cell_id as string;
		render([{ ...cell(id), draws: false }], { sugars: [write], specs: WITH_DEFAULT });
		expect(row(id).hidden).toBe(false);
		expect(endLine().value).toBe("hi");
		// Typing on goes on from it, offered afresh: the sugar makes another cell.
		typeInto(endLine(), "hi!");
		expect(notify).toHaveBeenCalledTimes(2);
		expect(endLine().value).toBe("hi!");
	});

	it("gives the text back when the cell draws and no document comes with it", async () => {
		render([], { sugars: [write], specs: WITH_DEFAULT });
		act(() => endLine().focus());
		typeInto(endLine(), "hello");
		press(endLine(), "Enter");
		typeInto(endLine(), "there");
		const id = notify.mock.calls[0][1].cell_id as string;
		render([cell(id)], { sugars: [write], specs: WITH_DEFAULT });
		expect(row(id).hidden).toBe(true);
		await draw(id, "TestPlain");
		expect(row(id).hidden).toBe(false);
		expect(readEditor(VIEWER, "p1").requests).toEqual([]);
		expect(endLine().value).toBe("hello there");
	});

	it("is consumed, not given back, when what the cell draws is its document", async () => {
		const d = fakeDoc();
		drawnDoc = d.doc;
		render([], { sugars: [write], specs: WITH_DEFAULT });
		act(() => endLine().focus());
		typeInto(endLine(), "hi");
		const id = notify.mock.calls[0][1].cell_id as string;
		render([cell(id)], { sugars: [write], specs: WITH_DEFAULT });
		await draw(id, "TestDoc");
		drawnDoc = null;
		expect(d.doc.type).toHaveBeenCalledExactlyOnceWith("hi");
		expect(endLine().value).toBe("");
		expect(row(id).hidden).toBe(false);
	});
});

describe("one request pulls", () => {
	it("the caret arriving in an input line settles a landing cell's request", () => {
		render([cell("a")]);
		press(endLine(), "/");
		typeInto(endLine(), "text");
		press(endLine(), "Enter");
		const id = notify.mock.calls[0][1].cell_id as string;
		render([cell("a"), cell(id)]);
		expect(selected()).toEqual([id]);
		// Tab from the selection into the end line: nothing else settles it.
		expect(readEditor(VIEWER, "p1").requests.some((r) => r.pull)).toBe(true);
		act(() => endLine().focus());
		expect(readEditor(VIEWER, "p1").requests.some((r) => r.pull)).toBe(false);
		const doc = mountDoc(id);
		expect(doc.doc.focus).not.toHaveBeenCalled();
		expect(document.activeElement).toBe(endLine());
	});

	it("waking the line that feeds a request makes it the only one that pulls", () => {
		const write: Sugar = {
			class: "prose",
			onInput: (after, i, api) => {
				api.create({ after }, "text", { at: "end", text: i.kind === "text" ? i.text : "" });
				return true;
			},
		};
		render([cell("a")], { sugars: [write], specs: WITH_DEFAULT });
		act(() => endLine().focus());
		typeInto(endLine(), "hi");
		act(() => endLine().blur());
		expect(readEditor(VIEWER, "p1").requests.map((r) => r.pull)).toEqual([false]);
		act(() => endLine().focus());
		const pulls = readEditor(VIEWER, "p1").requests.filter((r) => r.pull);
		expect(pulls.map((r) => r.line)).toEqual(["end"]);
	});
});

describe("the plane handle", () => {
	it("starts a box selection from a press in the pane", () => {
		render([cell("a"), cell("b"), cell("c")]);
		["a", "b", "c"].forEach((id, i) => {
			row(id).getBoundingClientRect = () => new DOMRect(0, i * 40, 600, 40);
		});
		act(() =>
			handle.current?.press({
				button: 0,
				target: planeRoot(),
				clientX: 700,
				clientY: 10,
			} as unknown as React.PointerEvent),
		);
		act(() => {
			window.dispatchEvent(new MouseEvent("pointermove", { clientX: 500, clientY: 50 }));
			window.dispatchEvent(new MouseEvent("pointerup", { clientX: 500, clientY: 50 }));
		});
		expect(selected()).toEqual(["a", "b"]);
	});

	it("is cleared when the plane goes", () => {
		render([]);
		expect(handle.current).not.toBeNull();
		act(() => root.render(null));
		expect(handle.current).toBeNull();
	});
});
