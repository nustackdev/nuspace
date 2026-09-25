// Type to create, rendered in jsdom: a letter in the ghost starts a draft and
// a text cell, and the draft's text lands in the cell's editor once it mounts.
// Then the text cell's own keys: Cmd+Enter opens a ghost below it, Backspace
// when empty removes it. Then the title's way in: a ghost at the top.
//
// The editor is a stand-in node type drawing a bare contenteditable, and the
// browser's insert is a spy: jsdom edits neither on its own.

import { register, TooltipProvider, tree } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Plane } from "./Plane";
import { type ActivePlane, type Cell, type SlashSnippet, TEXT } from "./types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

register("TestEditor", {
	component: () => <div contentEditable suppressContentEditableWarning tabIndex={-1} />,
});

const VIEWER = ["viewer"];
const SNIPPETS: SlashSnippet[] = [
	{ name: "program", label: "Program" },
	{ name: TEXT, label: "Text" },
];

let host: HTMLDivElement;
let root: Root;
const notify = vi.fn();
const insert = vi.fn(() => true);

const openRef: { current: ((home: () => void) => boolean) | null } = { current: null };

function render(cells: Cell[], snippets = SNIPPETS, editable = true) {
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
					snippets={snippets}
					editable={editable}
					wide={false}
					compact={false}
					notify={notify}
					openRef={openRef}
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
	document.execCommand = insert;
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
	tree.getState().remove(VIEWER);
});

describe("typing into the ghost", () => {
	it("starts a draft and a cell from the flagged snippet, then hands the text off", async () => {
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

	it("opens the / search as before when no text snippet is registered", () => {
		render([], [{ name: "program", label: "Program" }]);
		typeInto(ghost() as HTMLInputElement, "h");
		expect(notify).not.toHaveBeenCalled();
		expect(draftBox()).toBeNull();
		expect(ghost()?.value).toBe("h");
		expect(ghost()?.placeholder).toBe("Type to search");
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
		render([cell("b")], SNIPPETS, false);
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
		expect(notify).toHaveBeenCalledWith("cell.delete", { plane_id: "p1", cell_id: "b" });
		expect(document.activeElement).toBe(above);
	});
});

describe("Enter at the end of the title", () => {
	it("opens a ghost at the top, and Escape goes home", async () => {
		render([cell("a")]);
		await mountEditor("a");
		const home = vi.fn();
		act(() => {
			openRef.current?.(home);
		});
		const top = ghosts()[0];
		expect(ghosts()).toHaveLength(2);
		expect(document.activeElement).toBe(top);
		const first = host.querySelector('[data-cell="a"]') as HTMLElement;
		expect(top.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
		press(top, "Escape");
		expect(home).toHaveBeenCalledTimes(1);
		expect(ghosts()).toHaveLength(1);
	});

	it("does nothing without a text snippet, or on a read-only plane", () => {
		render([cell("a")], [{ name: "program", label: "Program" }]);
		expect(openRef.current?.(() => {})).toBe(false);
		render([cell("a")], SNIPPETS, false);
		expect(openRef.current).toBeNull();
	});
});
