// The source editor's boundary, against the kit's real code block: which keys
// leave the cell and which stay in it, and that a read-only source never
// saves or runs.

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FocusReq } from "../state";
import { SourceEditor } from "./Code";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
// jsdom lays nothing out, and the editor measures text ranges to move a caret.
Range.prototype.getClientRects = () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect = () => new DOMRect();

const SOURCE = "x = 1\ny = 2\nz = 3";

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

async function mount(readOnly: boolean, focusReq: FocusReq | null = null) {
	const calls = { onCommit: vi.fn(), onExit: vi.fn(), onEscape: vi.fn() };
	await act(async () => {
		root.render(
			<SourceEditor
				source={SOURCE}
				focusReq={focusReq}
				onFocusConsumed={() => {}}
				readOnly={readOnly}
				{...calls}
			/>,
		);
	});
	const content = host.querySelector<HTMLElement>(".cm-content");
	if (!content) throw new Error("no code block mounted");
	return { ...calls, content };
}

function press(el: HTMLElement, key: string, mod = false) {
	act(() => {
		el.dispatchEvent(
			new KeyboardEvent("keydown", { key, metaKey: mod, bubbles: true, cancelable: true }),
		);
	});
}

describe("a read-only source", () => {
	it("is built read-only", async () => {
		const { content } = await mount(true);
		expect(content.getAttribute("contenteditable")).toBe("false");
	});

	it("still takes the caret, so the keyboard can pass through it", async () => {
		const { content } = await mount(true);
		expect(content.tabIndex).toBe(0);
	});

	it("never saves or runs, on mod+enter or Escape", async () => {
		const { content, onCommit, onEscape } = await mount(true);
		press(content, "Enter", true);
		press(content, "Escape");
		expect(onCommit).not.toHaveBeenCalled();
		expect(onEscape).toHaveBeenCalledOnce();
	});

	it("is one stop: either arrow leaves it from any line", async () => {
		const { content, onExit } = await mount(true);
		press(content, "ArrowDown");
		press(content, "ArrowUp");
		expect(onExit.mock.calls.map(([dir]) => dir)).toEqual(["down", "up"]);
	});
});

describe("an editable source", () => {
	it("is built editable", async () => {
		const { content } = await mount(false);
		expect(content.getAttribute("contenteditable")).toBe("true");
	});

	it("leaves from its last line downward, carrying the column", async () => {
		const { content, onExit } = await mount(false, { cellId: "c", place: "end" });
		press(content, "ArrowDown");
		expect(onExit).toHaveBeenCalledWith("down", 5);
	});

	it("leaves from its first line upward, carrying the column", async () => {
		const { content, onExit } = await mount(false, { cellId: "c", place: "start", column: 2 });
		press(content, "ArrowUp");
		expect(onExit).toHaveBeenCalledWith("up", 2);
	});

	it("stays put on an arrow toward its inside", async () => {
		const top = await mount(false, { cellId: "c", place: "start" });
		press(top.content, "ArrowDown");
		expect(top.onExit).not.toHaveBeenCalled();
		const bottom = await mount(false, { cellId: "c", place: "end" });
		press(bottom.content, "ArrowUp");
		expect(bottom.onExit).not.toHaveBeenCalled();
	});

	it("a modified arrow never leaves", async () => {
		const { content, onExit } = await mount(false, { cellId: "c", place: "start" });
		press(content, "ArrowUp", true);
		expect(onExit).not.toHaveBeenCalled();
	});

	it("Escape hands back without a save when nothing changed", async () => {
		const { content, onCommit, onEscape } = await mount(false);
		press(content, "Escape");
		expect(onEscape).toHaveBeenCalledOnce();
		expect(onCommit).not.toHaveBeenCalled();
	});
});
