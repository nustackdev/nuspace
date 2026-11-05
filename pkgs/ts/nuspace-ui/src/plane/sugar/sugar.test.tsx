// The text sugar, rendered in jsdom, rule by rule (./useTextSugar.ts). R1: a
// letter or Enter in the ghost starts a draft and a text cell, and the
// draft's text lands in the cell's editor once it mounts. Then the text
// cell's own keys: R7 Cmd+Enter opens a ghost below it, R2 Backspace when
// blank removes it, R6 `/` when blank stands a ghost in for it. Then R5, the
// title's way in: an empty text cell at the top.
//
// The editor is a stand-in node type drawing a bare contenteditable, and the
// browser's insert is a spy: jsdom edits neither on its own.

import { register, TooltipProvider, tree } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Plane } from "../Plane";
import { type ActivePlane, type Cell, type CellSpec, TEXT } from "../types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// The slash menu's popover sizes itself with a ResizeObserver, which jsdom lacks.
globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;

register("TestEditor", {
	component: () => <div contentEditable suppressContentEditableWarning tabIndex={-1} />,
});

const VIEWER = ["viewer"];
const CELL_SPECS: CellSpec[] = [
	{ name: "program", label: "Program" },
	{ name: TEXT, label: "Text" },
];

let host: HTMLDivElement;
let root: Root;
const notify = vi.fn();
const insert = vi.fn(() => true);

const openRef: { current: (() => boolean) | null } = { current: null };
const titleEnd = vi.fn();
const titleEndRef: { current: (() => void) | null } = { current: titleEnd };
const entryRef: { current: (() => boolean) | null } = { current: null };

function render(cells: Cell[], cellSpecs = CELL_SPECS, editable = true) {
	const plane: ActivePlane = {
		plane_id: "p1",
		title: "",
		meta: { editable, full_width: false, compact: false },
		cells,
	};
	act(() => {
		root.render(
			<TooltipProvider>
				<Plane
					viewerPath={VIEWER}
					plane={plane}
					cellSpecs={cellSpecs}
					editable={editable}
					wide={false}
					compact={false}
					notify={notify}
					openRef={openRef}
					titleEndRef={titleEndRef}
					entryRef={entryRef}
				/>
			</TooltipProvider>,
		);
	});
}

function cell(id: string, made_by = TEXT): Cell {
	return {
		id,
		name: made_by,
		source: "",
		made_by,
		has_ui: null,
		classes: made_by === TEXT ? ["prose"] : [],
		status: { cell_id: id, state: "running", error: null, started_at: null },
	};
}

/** Mount a cell's editor, as its program's first write would. */
async function mountEditor(id: string) {
	await act(async () => {
		tree.getState().write([["viewer"], ["cells"], [id], ["text", "TestEditor"]], { value: "" });
	});
	return host.querySelector<HTMLElement>(`[data-cell="${id}"] [contenteditable]`) as HTMLElement;
}

function press(el: HTMLElement, key: string, init: KeyboardEventInit = {}) {
	act(() => {
		el.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, ...init }));
	});
}

/** Type into a field the way React hears it: native setter, then `input`. */
function typeInto(el: HTMLInputElement | HTMLTextAreaElement, value: string) {
	const proto = Object.getPrototypeOf(el);
	act(() => {
		Object.getOwnPropertyDescriptor(proto, "value")?.set?.call(el, value);
		el.dispatchEvent(new Event("input", { bubbles: true }));
	});
}

/** The caret at `offset` in `node`. */
function placeAt(node: Node, offset: number) {
	(node.parentElement as HTMLElement | null)?.focus();
	const at = document.createRange();
	at.setStart(node, offset);
	document.getSelection()?.removeAllRanges();
	document.getSelection()?.addRange(at);
}

const ghosts = () => [...host.querySelectorAll<HTMLInputElement>("input[aria-label='New cell']")];
const ghost = () => ghosts()[0] ?? null;
const draftBox = () => host.querySelector<HTMLTextAreaElement>("textarea");

beforeEach(() => {
	tree.getState().write([["viewer"]], {});
	host = document.createElement("div");
	document.body.appendChild(host);
	root = createRoot(host);
	notify.mockClear();
	insert.mockClear();
	titleEnd.mockClear();
	document.execCommand = insert;
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
	tree.getState().remove(VIEWER);
});

describe("typing into the ghost", () => {
	it("starts a draft and a cell from the text cell spec, then hands the text off", async () => {
		render([]);
		typeInto(ghost() as HTMLInputElement, "h");

		expect(notify).toHaveBeenCalledTimes(1);
		const [op, args] = notify.mock.calls[0];
		expect(op).toBe("cell.create");
		expect(args).toMatchObject({ plane_id: "p1", name: TEXT, index: 0 });
		const box = draftBox() as HTMLTextAreaElement;
		expect(box.value).toBe("h");
		expect(document.activeElement).toBe(box);

		typeInto(box, "hello");
		expect(draftBox()?.value).toBe("hello");

		// The cell arrives with nothing drawn yet: hidden, the draft stays.
		const id = args.cell_id as string;
		render([cell(id)]);
		expect(host.querySelector(`[data-cell="${id}"]`)?.hasAttribute("hidden")).toBe(true);
		expect(draftBox()).not.toBeNull();

		// Its editor mounts with its first value: the text goes in, the draft goes.
		await act(async () => {
			tree.getState().write([["viewer"], ["cells"], [id], ["text", "TestEditor"]], { value: "" });
		});
		expect(insert).toHaveBeenCalledWith("insertText", false, "hello");
		expect(draftBox()).toBeNull();
		const row = host.querySelector(`[data-cell="${id}"]`);
		expect(row?.hasAttribute("hidden")).toBe(false);
		expect(document.activeElement).toBe(row?.querySelector("[contenteditable]"));
	});

	it("starts an empty text cell on Enter, not a program", () => {
		render([]);
		press(ghost() as HTMLInputElement, "Enter");
		expect(notify).toHaveBeenCalledTimes(1);
		expect(notify.mock.calls[0][1]).toMatchObject({ name: TEXT, index: 0 });
		expect(draftBox()?.value).toBe("");
	});

	it("says what it does, with the sugar and without", () => {
		render([]);
		expect(ghost()?.placeholder).toBe("Write, or press / for cells");
		render([], [{ name: "program", label: "Program" }]);
		expect(ghost()?.placeholder).toBe("Press / for cells");
	});

	it("opens the / search as before when no text cell spec is registered", () => {
		render([], [{ name: "program", label: "Program" }]);
		typeInto(ghost() as HTMLInputElement, "h");
		expect(notify).not.toHaveBeenCalled();
		expect(draftBox()).toBeNull();
		expect(ghost()?.value).toBe("h");
		expect(ghost()?.placeholder).toBe("Type to search");
	});

	it("does nothing on Enter when no text cell spec is registered", () => {
		render([], [{ name: "program", label: "Program" }]);
		press(ghost() as HTMLInputElement, "Enter");
		expect(notify).not.toHaveBeenCalled();
		expect(draftBox()).toBeNull();
	});
});

describe("a text cell's keys", () => {
	it("Cmd+Enter opens a ghost right below, and typing there starts a text cell", async () => {
		render([cell("a"), cell("b")]);
		const editor = await mountEditor("a");
		press(editor, "Enter", { metaKey: true });
		expect(notify).not.toHaveBeenCalled();
		const [line, end] = ghosts();
		expect(ghosts()).toHaveLength(2);
		expect(document.activeElement).toBe(line);
		expect(line.compareDocumentPosition(end) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
		typeInto(line, "h");
		expect(notify.mock.calls[0][1]).toMatchObject({ name: TEXT, index: 1 });
		expect(document.activeElement).toBe(draftBox());
	});

	it("Escape in that ghost takes it away and puts the caret back", async () => {
		render([cell("a"), cell("b")]);
		const editor = await mountEditor("a");
		editor.textContent = "hello";
		const at = document.createRange();
		at.setStart(editor.firstChild as Node, 2);
		document.getSelection()?.removeAllRanges();
		document.getSelection()?.addRange(at);
		press(editor, "Enter", { metaKey: true });
		press(ghosts()[0], "Escape");
		expect(ghosts()).toHaveLength(1);
		expect(document.activeElement).toBe(editor);
		const sel = document.getSelection();
		expect([sel?.focusNode, sel?.focusOffset]).toEqual([editor.firstChild, 2]);
	});

	it("Cmd+Enter in the last cell lands in the end ghost, which stays on Escape", async () => {
		render([cell("a")]);
		const editor = await mountEditor("a");
		press(editor, "Enter", { metaKey: true });
		expect(ghosts()).toHaveLength(1);
		expect(document.activeElement).toBe(ghost());
		press(ghost() as HTMLInputElement, "Escape");
		expect(ghosts()).toHaveLength(1);
		expect(document.activeElement).toBe(editor);
	});

	it("Cmd+Enter does nothing in a cell of another kind, or on a read-only plane", async () => {
		render([cell("a", "program")]);
		press(await mountEditor("a"), "Enter", { metaKey: true });
		render([cell("b")], CELL_SPECS, false);
		press(await mountEditor("b"), "Enter", { metaKey: true });
		expect(notify).not.toHaveBeenCalled();
		expect(draftBox()).toBeNull();
	});

	it("Backspace in an empty one removes it and lands at the end of the one above", async () => {
		render([cell("a"), cell("b")]);
		const above = await mountEditor("a");
		above.textContent = "hello";
		const editor = await mountEditor("b");
		editor.textContent = "x";
		press(editor, "Backspace");
		expect(notify).not.toHaveBeenCalled();

		editor.textContent = "";
		press(editor, "Backspace");
		expect(notify).toHaveBeenCalledWith("cell.delete", { cell_id: "b" });
		expect(document.activeElement).toBe(above);
	});

	it("Backspace takes an empty line as blank, never an empty table", async () => {
		render([cell("a"), cell("b")]);
		await mountEditor("a");
		const editor = await mountEditor("b");
		editor.innerHTML = "<table><tr><td></td></tr></table>";
		press(editor, "Backspace");
		expect(notify).not.toHaveBeenCalled();
		editor.innerHTML = "<h2><br></h2>";
		press(editor, "Backspace");
		expect(notify).toHaveBeenCalledWith("cell.delete", { cell_id: "b" });
	});

	it("Backspace in the top one goes back to the title", async () => {
		render([cell("a")]);
		press(await mountEditor("a"), "Backspace");
		expect(notify).toHaveBeenCalledWith("cell.delete", { cell_id: "a" });
		expect(titleEnd).toHaveBeenCalledTimes(1);
	});

	it("leaves Cmd+Enter in a table to the table", async () => {
		render([cell("a"), cell("b")]);
		const editor = await mountEditor("a");
		editor.innerHTML = "<table><tbody><tr><td>x</td></tr></tbody></table>";
		const at = document.createRange();
		at.setStart(editor.querySelector("td")?.firstChild as Node, 1);
		document.getSelection()?.removeAllRanges();
		document.getSelection()?.addRange(at);
		press(editor, "Enter", { metaKey: true });
		expect(ghosts()).toHaveLength(1);
	});

	it("Shift+arrow at the text's edge goes on as a cell selection", async () => {
		render([cell("a"), cell("b", "program"), cell("c")]);
		await mountEditor("a");
		const editor = await mountEditor("c");
		editor.textContent = "hi";
		placeAt(editor.firstChild as Node, 1);
		press(editor, "ArrowLeft", { shiftKey: true });
		expect(document.activeElement).toBe(editor);
		placeAt(editor.firstChild as Node, 0);
		press(editor, "ArrowLeft", { shiftKey: true });
		const plane = host.querySelector<HTMLElement>("[tabindex='-1']") as HTMLElement;
		expect(document.activeElement).toBe(plane);
		// The cell above is a program: crossing selects any kind. Then the
		// plane's own Shift+Up goes on, and what is selected is what goes.
		press(plane, "ArrowUp", { shiftKey: true });
		press(plane, "Backspace");
		expect(notify.mock.calls.map((c) => c[1].cell_id)).toEqual(["a", "b", "c"]);
	});

	it("the arrows cross between the title and a text cell on top, both ways", async () => {
		render([cell("a")]);
		const editor = await mountEditor("a");
		editor.textContent = "hello";
		placeAt(editor.firstChild as Node, 0);
		press(editor, "ArrowLeft");
		expect(titleEnd).toHaveBeenCalledTimes(1);
		act(() => {
			entryRef.current?.();
		});
		expect(document.activeElement).toBe(editor);
	});

	it("Left at the start slides into the text cell above, Right at the end back", async () => {
		render([cell("a"), cell("b"), cell("c", "program")]);
		const above = await mountEditor("a");
		above.textContent = "hello";
		const editor = await mountEditor("b");
		editor.textContent = "world";
		placeAt(editor.firstChild as Node, 0);
		press(editor, "ArrowLeft");
		expect(document.activeElement).toBe(above);
		placeAt(above.firstChild as Node, 5);
		press(above, "ArrowRight");
		expect(document.activeElement).toBe(editor);
		// Mid-text the arrow is the editor's, and a program below is no text cell.
		placeAt(editor.firstChild as Node, 2);
		press(editor, "ArrowLeft");
		expect(document.activeElement).toBe(editor);
		placeAt(editor.firstChild as Node, 5);
		press(editor, "ArrowRight");
		expect(document.activeElement).toBe(editor);
	});
});

describe("a text drag out of its cell", () => {
	/** Rows stacked 40px apart, as the plane would lay them out. */
	function stack(ids: string[]) {
		ids.forEach((id, i) => {
			const r = host.querySelector(`[data-cell="${id}"]`) as HTMLElement;
			r.getBoundingClientRect = () => new DOMRect(0, i * 40, 600, 40);
		});
	}
	const pointer = (el: EventTarget, type: string, clientY: number) =>
		act(() => {
			el.dispatchEvent(new MouseEvent(type, { bubbles: true, button: 0, clientY }));
		});

	it("becomes a cell selection once it leaves the row", async () => {
		render([cell("a"), cell("b"), cell("c")]);
		const editor = await mountEditor("a");
		await mountEditor("b");
		stack(["a", "b", "c"]);
		pointer(editor, "pointerdown", 10);
		pointer(window, "pointermove", 30);
		expect(document.activeElement).not.toBe(host.querySelector("[tabindex='-1']"));
		pointer(window, "pointermove", 50);
		const plane = host.querySelector<HTMLElement>("[tabindex='-1']");
		expect(document.activeElement).toBe(plane);
		pointer(window, "pointerup", 50);
		// What it selected is what the selection keys act on: a and b.
		press(plane as HTMLElement, "Backspace");
		expect(notify.mock.calls).toEqual([
			["cell.delete", { cell_id: "a" }],
			["cell.delete", { cell_id: "b" }],
		]);
	});
});

describe("/ in a blank text cell", () => {
	const row = (id: string) => host.querySelector(`[data-cell="${id}"]`) as HTMLElement;

	it("stands a ghost in for it with the menu open, and Escape brings it back", async () => {
		render([cell("a"), cell("b")]);
		const editor = await mountEditor("a");
		press(editor, "/");
		expect(row("a").hasAttribute("hidden")).toBe(true);
		const line = ghosts()[0];
		expect(document.activeElement).toBe(line);
		expect(line.placeholder).toBe("Type to search");
		press(line, "Escape");
		expect(row("a").hasAttribute("hidden")).toBe(false);
		expect(ghosts()).toHaveLength(1);
		expect(document.activeElement).toBe(editor);
		expect(notify).not.toHaveBeenCalled();
	});

	it("replaces it with the pick", async () => {
		render([cell("a"), cell("b")]);
		press(await mountEditor("a"), "/");
		press(ghosts()[0], "Enter");
		expect(notify.mock.calls.map((c) => c[0])).toEqual(["cell.create", "cell.delete"]);
		expect(notify.mock.calls[0][1]).toMatchObject({ index: 1 });
		expect(notify.mock.calls[1][1]).toEqual({ cell_id: "a" });
	});

	it("keeps the replaced cell hidden until the server drops it", async () => {
		render([cell("a"), cell("b")]);
		press(await mountEditor("a"), "/");
		press(ghosts()[0], "Enter");
		expect(row("a").hasAttribute("hidden")).toBe(true);
		render([cell("b")]);
		expect(row("a")).toBeNull();
	});

	it("is the one menu line in the last cell's place", async () => {
		render([cell("a")]);
		press(await mountEditor("a"), "/");
		expect(ghosts()).toHaveLength(1);
		expect(ghosts()[0].placeholder).toBe("Type to search");
		press(ghosts()[0], "Escape");
		expect(ghosts()).toHaveLength(1);
		expect(row("a").hasAttribute("hidden")).toBe(false);
	});

	it("is only a slash in a cell with text in it", async () => {
		render([cell("a")]);
		const editor = await mountEditor("a");
		editor.textContent = "hi";
		press(editor, "/");
		expect(row("a").hasAttribute("hidden")).toBe(false);
		expect(ghosts()).toHaveLength(1);
	});
});

describe("Enter in the title", () => {
	it("starts an empty text cell at the top", async () => {
		render([cell("a")]);
		await mountEditor("a");
		let opened = false;
		act(() => {
			opened = openRef.current?.() ?? false;
		});
		expect(opened).toBe(true);
		expect(notify).toHaveBeenCalledTimes(1);
		expect(notify.mock.calls[0][1]).toMatchObject({ name: TEXT, index: 0 });
		const box = draftBox() as HTMLTextAreaElement;
		expect(box.value).toBe("");
		expect(document.activeElement).toBe(box);
		const first = host.querySelector('[data-cell="a"]') as HTMLElement;
		expect(box.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
	});

	it("does nothing without a text cell spec, or on a read-only plane", () => {
		render([cell("a")], [{ name: "program", label: "Program" }]);
		expect(openRef.current?.()).toBe(false);
		render([cell("a")], CELL_SPECS, false);
		expect(openRef.current).toBeNull();
	});
});
