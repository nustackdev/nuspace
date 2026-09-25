// The plane's title, renamed in place, rendered in jsdom.
//
// Typing is faked by writing the text node and firing the key or the blur the
// browser would: jsdom does not edit a contenteditable on its own.

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Title } from "./Title";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: Root;
const onCommit = vi.fn();
const onExit = vi.fn(() => true);
const onSplit = vi.fn((_tail: string) => true);
const onOpen = vi.fn((_home: () => void) => true);

function render(value: string, split = false) {
	act(() => {
		root.render(
			<Title
				value={value}
				placeholder="Untitled"
				onCommit={onCommit}
				onExit={onExit}
				onOpen={split ? onOpen : undefined}
				onSplit={split ? onSplit : undefined}
			/>,
		);
	});
}

const title = () => {
	const el = host.querySelector<HTMLHeadingElement>("h1");
	if (!el) throw new Error("no title");
	return el;
};

function type(text: string) {
	act(() => {
		title().focus();
		title().textContent = text;
	});
}

function key(k: string) {
	act(() => {
		title().dispatchEvent(
			new KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true }),
		);
	});
}

/** Put the caret at `offset` in the title's text. */
function caret(offset: number) {
	const node = title().firstChild ?? title();
	const range = document.createRange();
	range.setStart(node, offset);
	range.collapse(true);
	const sel = document.getSelection();
	sel?.removeAllRanges();
	sel?.addRange(range);
}

beforeEach(() => {
	host = document.createElement("div");
	document.body.appendChild(host);
	root = createRoot(host);
	onCommit.mockClear();
	onExit.mockClear();
	onSplit.mockClear();
	onOpen.mockClear();
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

describe("Title", () => {
	it("shows the server title, and a placeholder when there is none", () => {
		render("Notes");
		expect(title().textContent).toBe("Notes");
		expect(title().getAttribute("contenteditable")).toBe("true");
		render("");
		expect(title().textContent).toBe("");
		expect(title().dataset.placeholder).toBe("Untitled");
	});

	it("commits a changed title on Enter, trimmed", () => {
		render("Notes");
		type("  Plans  ");
		caret(2);
		key("Enter");
		expect(onCommit).toHaveBeenCalledExactlyOnceWith("Plans");
		expect(onExit).not.toHaveBeenCalled();
		expect(document.activeElement).not.toBe(title());
	});

	it("commits on blur, and not when nothing changed", () => {
		render("Notes");
		type("Notes ");
		act(() => title().blur());
		expect(onCommit).not.toHaveBeenCalled();
		type("Plans");
		act(() => title().blur());
		expect(onCommit).toHaveBeenCalledExactlyOnceWith("Plans");
	});

	it("reverts on Escape", () => {
		render("Notes");
		type("Plans");
		key("Escape");
		expect(onCommit).not.toHaveBeenCalled();
		expect(title().textContent).toBe("Notes");
		expect(document.activeElement).not.toBe(title());
	});

	it("keeps an empty title from committing", () => {
		render("Notes");
		type("   ");
		act(() => title().blur());
		expect(onCommit).not.toHaveBeenCalled();
		expect(title().textContent).toBe("Notes");
	});

	it("does not clobber the draft while focused, and resyncs once it lets go", () => {
		render("Notes");
		type("Pla");
		render("Renamed elsewhere");
		expect(title().textContent).toBe("Pla");
		key("Escape");
		expect(title().textContent).toBe("Renamed elsewhere");
		render("Again");
		expect(title().textContent).toBe("Again");
	});

	it("hands the caret down on Down or Enter at the end", () => {
		render("Notes");
		type("Notes");
		caret(5);
		key("ArrowDown");
		expect(onExit).toHaveBeenCalledTimes(1);
		caret(2);
		key("ArrowDown");
		expect(onExit).toHaveBeenCalledTimes(1);
		caret(5);
		key("Enter");
		expect(onExit).toHaveBeenCalledTimes(2);
	});

	it("splits on Enter: the tail opens a text cell, the head is the rename", () => {
		render("Notes", true);
		type("Plans today");
		caret(5);
		key("Enter");
		expect(onSplit).toHaveBeenCalledExactlyOnceWith("today");
		expect(onExit).not.toHaveBeenCalled();
		act(() => title().blur());
		expect(onCommit).toHaveBeenCalledExactlyOnceWith("Plans");
	});

	it("keeps the title whole on Enter at its start, and the cell opens empty", () => {
		render("Notes", true);
		type("Notes");
		caret(0);
		key("Enter");
		expect(onSplit).toHaveBeenCalledExactlyOnceWith("");
		expect(title().textContent).toBe("Notes");
	});

	it("opens a line on Enter at the end, and its way back lands at the end", () => {
		render("Notes", true);
		type("Notes");
		caret(5);
		key("Enter");
		expect(onOpen).toHaveBeenCalledTimes(1);
		expect(onSplit).not.toHaveBeenCalled();
		expect(onExit).not.toHaveBeenCalled();
		act(() => title().blur());
		caret(0);
		act(() => onOpen.mock.calls[0][0]());
		expect(document.activeElement).toBe(title());
		const sel = document.getSelection() as Selection;
		expect(sel.isCollapsed).toBe(true);
		const rest = document.createRange();
		rest.selectNodeContents(title());
		rest.setStart(sel.focusNode as Node, sel.focusOffset);
		expect(rest.toString()).toBe("");
	});

	it("leaves as before when there is nothing to split into", () => {
		onOpen.mockReturnValueOnce(false);
		onSplit.mockReturnValueOnce(false);
		render("Notes", true);
		type("Notes");
		caret(5);
		key("Enter");
		expect(onExit).toHaveBeenCalledTimes(1);
	});
});
