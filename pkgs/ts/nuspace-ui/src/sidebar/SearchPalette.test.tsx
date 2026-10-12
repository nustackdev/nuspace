// The search popup, rendered in jsdom: where to look ticks by row, by group
// and all at once, groups fold, and the search sends only what is ticked.

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SearchPopup } from "./SearchPalette";
import { closeSearch, openSearch, setFold, setKinds, TITLES } from "./search";
import type { Searchable } from "./types";

vi.mock("../core/router", () => ({ replacePane: vi.fn() }));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;
Element.prototype.scrollIntoView ??= () => {};

const entry = (name: string, label: string, group: string): Searchable => ({
	name,
	label,
	group,
	icon: "",
	description: "",
});

const searchable = [
	entry("note", "Note", "Writing"),
	entry("todo", "Todo", "Writing"),
	entry("movie", "Movie", "Media"),
];

let host: HTMLDivElement;
let root: Root;
const notify = vi.fn();

beforeEach(() => {
	notify.mockClear();
	// The store outlives a render: start every test ticked and unfolded.
	setKinds([TITLES, ...searchable.map((s) => s.name)], true);
	setFold("Writing", false);
	setFold("Media", false);
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
	act(() => root.render(<SearchPopup searchable={searchable} notify={notify} />));
	act(() => openSearch());
});

afterEach(() => {
	act(() => closeSearch());
	act(() => root.unmount());
	host.remove();
});

const values = () =>
	[...document.querySelectorAll('[cmdk-item=""]')].map((i) => i.getAttribute("data-value"));

const row = (value: string) => {
	const el = document.querySelector<HTMLElement>(`[cmdk-item=""][data-value="${value}"]`);
	if (!el) throw new Error(`no row ${value}`);
	return el;
};

const box = (value: string) =>
	row(value).querySelector("[role=checkbox]")?.getAttribute("data-state");

const input = () => {
	const el = document.querySelector<HTMLInputElement>("[cmdk-input]");
	if (!el) throw new Error("no input");
	return el;
};

const type = (text: string) =>
	act(() => {
		const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
		set?.call(input(), text);
		input().dispatchEvent(new Event("input", { bubbles: true }));
	});

const press = (key: string) =>
	act(() => {
		input().dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
	});

describe("SearchPopup", () => {
	it("lists everywhere, titles, then each group over its snippets", () => {
		expect(values()).toEqual([
			"all",
			"titles",
			"group:Writing",
			"snippet:note",
			"snippet:todo",
			"group:Media",
			"snippet:movie",
		]);
	});

	it("ticks a whole group from its row, and shows it partly ticked", () => {
		act(() => row("snippet:note").click());
		expect(box("group:Writing")).toBe("indeterminate");
		expect(box("all")).toBe("indeterminate");
		act(() => row("group:Writing").click());
		expect(box("snippet:note")).toBe("checked");
		act(() => row("group:Writing").click());
		expect(box("snippet:note")).toBe("unchecked");
		expect(box("snippet:todo")).toBe("unchecked");
	});

	it("unticks and ticks everything from the All row", () => {
		act(() => row("all").click());
		expect(box("titles")).toBe("unchecked");
		expect(box("snippet:movie")).toBe("unchecked");
		act(() => row("all").click());
		expect(box("titles")).toBe("checked");
	});

	it("folds a group from its chevron", () => {
		act(() => row("group:Writing").querySelector<HTMLElement>("[data-open]")?.click());
		expect(values()).not.toContain("snippet:note");
		expect(box("group:Writing")).toBe("checked");
	});

	it("ticks the lit row on Tab and folds the lit group on Left", () => {
		press("ArrowDown");
		press("ArrowDown");
		expect(row("group:Writing").getAttribute("data-selected")).toBe("true");
		press("Tab");
		expect(box("snippet:note")).toBe("unchecked");
		press("ArrowLeft");
		expect(values()).not.toContain("snippet:note");
		press("ArrowRight");
		expect(values()).toContain("snippet:note");
	});

	it("searches only where it is ticked", () => {
		act(() => row("group:Writing").click());
		act(() => row("titles").click());
		type("tomato");
		press("Enter");
		expect(notify).toHaveBeenCalledWith("search.run", {
			query: "tomato",
			snippets: ["movie"],
			titles: false,
		});
	});
});
