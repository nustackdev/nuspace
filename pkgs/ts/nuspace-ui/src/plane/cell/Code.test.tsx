// The source editor's boundary, against the kit's real code block: which keys
// leave the cell and which stay in it, that a read-only source never saves or
// runs, and that an editable one saves (and so runs) on the submit alone.

import { EditorView } from "@codemirror/view";
import { SAVE_DELAY } from "@nustackdev/ui-kit";
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

/** A request for this source, at its start or end. */
function req(at: "start" | "end", column?: number): FocusReq {
	return { id: 1, cellId: "c", to: "source", at, column, pull: true };
}

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

function press(el: HTMLElement, key: string, mod = false, shift = false) {
	act(() => {
		el.dispatchEvent(
			new KeyboardEvent("keydown", {
				key,
				metaKey: mod,
				shiftKey: shift,
				bubbles: true,
				cancelable: true,
			}),
		);
	});
}

describe("a read-only source", () => {
	it("has no foot: there is nothing to save", async () => {
		await mount(true);
		expect(host.querySelector("[data-source-foot]")).toBeNull();
	});

	it("is built read-only", async () => {
		const { content } = await mount(true);
		expect(content.getAttribute("contenteditable")).toBe("false");
	});

	it("still takes the caret, so the keyboard can pass through it", async () => {
		const { content } = await mount(true);
		expect(content.tabIndex).toBe(0);
	});

	it("never saves or runs, on shift+enter, mod+enter or Escape", async () => {
		const { content, onCommit, onEscape } = await mount(true);
		press(content, "Enter", false, true);
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
		const { content, onExit } = await mount(false, req("end"));
		press(content, "ArrowDown");
		expect(onExit).toHaveBeenCalledWith("down", 5);
	});

	it("leaves from its first line upward, carrying the column", async () => {
		const { content, onExit } = await mount(false, req("start", 2));
		press(content, "ArrowUp");
		expect(onExit).toHaveBeenCalledWith("up", 2);
	});

	it("stays put on an arrow toward its inside", async () => {
		const top = await mount(false, req("start"));
		press(top.content, "ArrowDown");
		expect(top.onExit).not.toHaveBeenCalled();
		const bottom = await mount(false, req("end"));
		press(bottom.content, "ArrowUp");
		expect(bottom.onExit).not.toHaveBeenCalled();
	});

	it("a modified arrow never leaves", async () => {
		const { content, onExit } = await mount(false, req("start"));
		press(content, "ArrowUp", true);
		expect(onExit).not.toHaveBeenCalled();
	});

	it("keeps one foot line under it, saying how to save and close", async () => {
		await mount(false);
		const foot = host.querySelector("[data-source-foot]");
		expect(foot?.textContent).toContain("save");
		expect(foot?.textContent).toContain("close");
	});

	it("Escape hands back without a save when nothing changed", async () => {
		const { content, onCommit, onEscape } = await mount(false);
		press(content, "Escape");
		expect(onEscape).toHaveBeenCalledWith(false);
		expect(onCommit).not.toHaveBeenCalled();
	});
});

/** Type at the end of the source, the way the keyboard would. */
function typeEnd(content: HTMLElement, text: string) {
	const view = EditorView.findFromDOM(content) as EditorView;
	act(() => {
		view.focus();
		const end = view.state.doc.length;
		view.dispatch({
			changes: { from: end, insert: text },
			selection: { anchor: end + text.length },
		});
	});
}

const wait = (ms: number) =>
	act(async () => {
		await new Promise((r) => setTimeout(r, ms));
	});

describe("saving is the submit, and only the submit", () => {
	it("runs on shift+enter with the edited text", async () => {
		const { content, onCommit } = await mount(false);
		typeEnd(content, "\nw = 4");
		press(content, "Enter", false, true);
		expect(onCommit).toHaveBeenCalledWith(`${SOURCE}\nw = 4`);
	});

	it("never runs on a quiet moment, a blur or Escape, and Escape keeps the edits open", async () => {
		const { content, onCommit, onEscape } = await mount(false);
		typeEnd(content, "\nw = 4");
		await wait(SAVE_DELAY + 100);
		const away = document.createElement("button");
		document.body.append(away);
		act(() => away.focus());
		await wait(50);
		away.remove();
		press(content, "Escape");
		expect(onCommit).not.toHaveBeenCalled();
		expect(onEscape).toHaveBeenCalledWith(true);
		expect(host.querySelector("[data-source-foot]")?.textContent).toContain("unsaved");
	});

	it("submits on shift+enter even when nothing changed: a rerun is the intent", async () => {
		const { content, onCommit } = await mount(false);
		press(content, "Enter", false, true);
		expect(onCommit).toHaveBeenCalledWith(SOURCE);
	});
});
