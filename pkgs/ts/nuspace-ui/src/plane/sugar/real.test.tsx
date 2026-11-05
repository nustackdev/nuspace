// The text sugar against the kit's real markdown editor, the one a text cell
// draws. The editor marks Enter and Backspace handled whatever it does with
// them, which a bare stand-in (./sugar.test.tsx) never would: these keep the
// sugar ahead of it.

import { TooltipProvider, tree } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Plane } from "../Plane";
import { type Cell, TEXT } from "../types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
// jsdom lays nothing out, and the editor measures to move a caret.
Range.prototype.getClientRects = () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect = () => new DOMRect();
Element.prototype.scrollIntoView = () => {};
document.elementFromPoint = () => null;
globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;

let host: HTMLDivElement;
let root: Root;
const notify = vi.fn();

function cell(id: string): Cell {
	return {
		id,
		name: TEXT,
		source: "",
		made_by: TEXT,
		has_ui: true,
		classes: ["prose"],
		status: { cell_id: id, state: "running", error: null, started_at: null },
	};
}

async function render(ids: string[], texts: Record<string, string> = {}) {
	act(() => {
		root.render(
			<TooltipProvider>
				<Plane
					viewerPath={["viewer"]}
					plane={{
						plane_id: "p1",
						title: "",
						meta: { editable: true, full_width: false, compact: false },
						cells: ids.map(cell),
					}}
					cellSpecs={[{ name: TEXT, label: "Text" }]}
					editable
					wide={false}
					compact={false}
					notify={notify}
				/>
			</TooltipProvider>,
		);
	});
	for (const id of ids) {
		await act(async () => {
			tree.getState().write([["viewer"], ["cells"], [id], ["text", "MarkdownRef"]], {
				value: texts[id] ?? "",
				editable: true,
			});
		});
	}
}

const ghosts = () => host.querySelectorAll("input[aria-label='New cell']");
const editorOf = (id: string) =>
	host.querySelector<HTMLElement>(`[data-cell="${id}"] [contenteditable="true"]`) as HTMLElement;

function press(el: HTMLElement, key: string, init: KeyboardEventInit = {}) {
	act(() => {
		el.dispatchEvent(
			new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...init }),
		);
	});
}

beforeEach(() => {
	tree.getState().write([["viewer"]], {});
	host = document.createElement("div");
	document.body.appendChild(host);
	root = createRoot(host);
	notify.mockClear();
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
	tree.getState().remove(["viewer"]);
});

describe("a text cell drawn by the kit's editor", () => {
	it("Cmd+Enter opens a line below", async () => {
		await render(["a", "b"]);
		const editor = editorOf("a");
		editor.focus();
		press(editor, "Enter", { metaKey: true });
		expect(ghosts()).toHaveLength(2);
	});

	it("Backspace when blank deletes it", async () => {
		await render(["a", "b"]);
		const editor = editorOf("b");
		editor.focus();
		press(editor, "Backspace");
		expect(notify).toHaveBeenCalledWith("cell.delete", { cell_id: "b" });
	});

	it("Backspace mid-text is the editor's", async () => {
		await render(["a", "b"], { a: "hello", b: "world" });
		const editor = editorOf("b");
		editor.focus();
		const at = document.createRange();
		at.setStart(editor.querySelector("p")?.firstChild as Node, 2);
		document.getSelection()?.removeAllRanges();
		document.getSelection()?.addRange(at);
		press(editor, "Backspace");
		expect(notify).not.toHaveBeenCalled();
	});

	it("/ when blank stands the menu in for it", async () => {
		await render(["a", "b"]);
		const editor = editorOf("a");
		editor.focus();
		press(editor, "/");
		expect(host.querySelector('[data-cell="a"]')?.hasAttribute("hidden")).toBe(true);
	});
});
