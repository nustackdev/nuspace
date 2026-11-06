// The plane's title, renamed in place, rendered in jsdom.
//
// Typing is faked by writing the text node and firing the key or the blur the
// browser would: jsdom does not edit a contenteditable on its own.

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { TitleIntent } from "../plane/intents";
import { focusTitle, Title } from "./Title";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: Root;
const onCommit = vi.fn();
/** The plane below as the core has it: it takes the caret off the title's
 *  end, and leaves Enter mid-title to the title. */
const core = (i: TitleIntent) => i.kind === "leave" || i.end;
const onIntent = vi.fn(core);

function render(value: string) {
	act(() => {
		root.render(
			<Title value={value} placeholder="Untitled" onCommit={onCommit} onIntent={onIntent} />,
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
	onIntent.mockReset();
	onIntent.mockImplementation(core);
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
		expect(onIntent).toHaveBeenCalledExactlyOnceWith({ kind: "enter", end: false });
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

	it("reports Down, Right and Enter at the end, and arrows only there", () => {
		render("Notes");
		type("Notes");
		caret(5);
		key("ArrowDown");
		caret(2);
		key("ArrowDown");
		caret(5);
		key("Enter");
		key("ArrowRight");
		caret(2);
		key("ArrowRight");
		expect(onIntent.mock.calls.map(([i]) => i)).toEqual([
			{ kind: "leave", dir: "down" },
			{ kind: "enter", end: true },
			{ kind: "leave", dir: "right" },
		]);
	});

	it("keeps the title whole when the plane takes Enter mid-title", () => {
		onIntent.mockImplementation(() => true);
		render("Notes");
		type("Plans today");
		caret(5);
		key("Enter");
		expect(onIntent).toHaveBeenCalledExactlyOnceWith({ kind: "enter", end: false });
		expect(title().textContent).toBe("Plans today");
		expect(document.activeElement).toBe(title());
		act(() => title().blur());
		expect(onCommit).toHaveBeenCalledExactlyOnceWith("Plans today");
	});

	it("blurs on Enter at the end when the plane has nowhere to take it", () => {
		onIntent.mockImplementation(() => false);
		render("Notes");
		type("Notes");
		caret(5);
		key("Enter");
		expect(onIntent).toHaveBeenCalledTimes(1);
		expect(document.activeElement).not.toBe(title());
	});

	it("takes the caret back at its end through focusTitle", () => {
		render("Notes");
		type("Notes");
		act(() => title().blur());
		caret(0);
		act(() => focusTitle(title(), "end"));
		expect(document.activeElement).toBe(title());
		const sel = document.getSelection() as Selection;
		expect(sel.isCollapsed).toBe(true);
		const rest = document.createRange();
		rest.selectNodeContents(title());
		rest.setStart(sel.focusNode as Node, sel.focusOffset);
		expect(rest.toString()).toBe("");
	});
});
