// The pane router in jsdom, on the kit's real History: every move is a push
// or a replace with the layout as the entry's state, the URL is always the
// focused pane, back brings a layout back, "/" lands on /home, and the
// gesture rule sends plain and Option clicks to the right move and leaves
// the rest native.

import { catchAnchors, History } from "@nustackdev/ui-kit";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Layout } from "./layout";
import {
	closePane,
	closePanes,
	currentLayout,
	currentRoutes,
	ensureLanding,
	focusedRoute,
	focusPane,
	hrefFor,
	movePane,
	onReveal,
	openAt,
	openBeside,
	openHere,
	openInNewTab,
	paneRule,
} from "./router";

const pane = (plane: string, params: Record<string, string> = {}) => ({ plane, params });

/** Land on `path`, with `layout` as the entry's state (none when left out). */
function at(path: string, layout: Layout | null = null) {
	window.history.replaceState(layout, "", path);
}

const url = () => window.location.pathname + window.location.search;

/** The next History move, once it lands (back and forward land later). */
function nextMove(): Promise<void> {
	return new Promise((resolve) => {
		const off = History.subscribe(() => {
			off();
			resolve();
		});
	});
}

describe("landing", () => {
	it("is one pane off a copied link, with its query", () => {
		at("/movie?id=42");
		expect(currentLayout()).toEqual({ panes: [pane("movie", { id: "42" })], focus: 0 });
		expect(focusedRoute()).toBe("movie");
	});

	it("replaces / and anything that names no plane with /home", () => {
		at("/");
		const before = window.history.length;
		ensureLanding();
		expect(url()).toBe("/home");
		expect(window.history.length).toBe(before);
		at("/a/b");
		ensureLanding();
		expect(url()).toBe("/home");
		at("/a");
		ensureLanding();
		expect(url()).toBe("/a");
	});

	it("redirects a later entry on / too, after it lands", async () => {
		at("/a");
		ensureLanding();
		History.push("/");
		await Promise.resolve();
		expect(url()).toBe("/home");
	});

	it("brings a reloaded layout back from the entry's state", () => {
		const layout = { panes: [pane("a"), pane("movie", { id: "1" })], focus: 1 };
		at("/movie?id=1", layout);
		expect(currentLayout()).toEqual(layout);
	});
});

describe("moves", () => {
	beforeEach(() => at("/a"));

	it("pushes a link into the focused pane, the URL its target", () => {
		const before = window.history.length;
		openHere(pane("movie", { id: "42" }));
		expect(url()).toBe("/movie?id=42");
		expect(window.history.length).toBe(before + 1);
		expect(window.history.state).toEqual({ panes: [pane("movie", { id: "42" })], focus: 0 });
	});

	it("pushes Option beside the focused pane, focus and URL moving to it", () => {
		at("/b", { panes: [pane("a"), pane("b"), pane("c")], focus: 1 });
		openBeside(pane("x", { k: "v" }));
		expect(currentRoutes()).toEqual(["a", "b", "x", "c"]);
		expect(url()).toBe("/x?k=v");
	});

	it("replaces on focus: the URL follows, no entry", () => {
		at("/a", { panes: [pane("a"), pane("movie", { id: "1" })], focus: 0 });
		const before = window.history.length;
		focusPane("movie");
		expect(url()).toBe("/movie?id=1");
		expect(window.history.length).toBe(before);
		expect(currentRoutes()).toEqual(["a", "movie"]);
	});

	it("pushes a close, a reorder and a drop", () => {
		at("/a", { panes: [pane("a"), pane("b"), pane("c")], focus: 0 });
		const before = window.history.length;
		openAt("d", 1);
		expect(currentRoutes()).toEqual(["a", "d", "b", "c"]);
		movePane("a", 3);
		expect(currentRoutes()).toEqual(["d", "b", "c", "a"]);
		closePane("b");
		expect(currentRoutes()).toEqual(["d", "c", "a"]);
		expect(window.history.length).toBe(before + 3);
		expect(url()).toBe("/a");
	});

	it("replaces a close of a deleted plane, and lands home on the last", () => {
		const before = window.history.length;
		closePanes(["a"], true);
		expect(url()).toBe("/home");
		expect(window.history.length).toBe(before);
	});

	it("reveals a pane asked for while open", () => {
		at("/a", { panes: [pane("a"), pane("b")], focus: 0 });
		const seen: string[] = [];
		const off = onReveal((id) => seen.push(id));
		openHere("b");
		expect(seen).toEqual(["b"]);
		expect(url()).toBe("/b");
		off();
	});

	it("opens a program's push in the focused pane, every other pane kept", async () => {
		at("/b", { panes: [pane("a"), pane("b")], focus: 1 });
		ensureLanding();
		// A program's HistoryRef.push: a URL and no layout.
		History.push("/movie?id=7");
		expect(currentLayout()).toEqual({ panes: [pane("a"), pane("movie", { id: "7" })], focus: 1 });
		expect(url()).toBe("/movie?id=7");
		// Landing writes the layout into that entry once the move is heard.
		await Promise.resolve();
		expect(History.current().state).toEqual(currentLayout());
		// Back is the desk as it was.
		const back = nextMove();
		History.back();
		await back;
		expect(currentLayout()).toEqual({ panes: [pane("a"), pane("b")], focus: 1 });
	});

	it("focuses a pane a program pushes to when it is already open", () => {
		at("/a", { panes: [pane("a"), pane("b")], focus: 0 });
		History.push("/b?k=v");
		expect(currentLayout()).toEqual({ panes: [pane("a"), pane("b", { k: "v" })], focus: 1 });
	});

	it("opens a plane in a new browser tab with its pane's params", () => {
		at("/a b?k=v");
		const open = vi.spyOn(window, "open").mockReturnValue(null);
		openInNewTab("a b");
		expect(open).toHaveBeenCalledWith("/a%20b?k=v", "_blank", "noopener");
		expect(hrefFor("x")).toBe("/x");
		open.mockRestore();
	});
});

describe("back and forward", () => {
	it("restores the layout the entry held", async () => {
		at("/a");
		openBeside("b");
		openBeside("c");
		expect(currentRoutes()).toEqual(["a", "b", "c"]);
		const landed = nextMove();
		History.back();
		await landed;
		expect(currentRoutes()).toEqual(["a", "b"]);
		expect(url()).toBe("/b");
		const again = nextMove();
		History.forward();
		await again;
		expect(currentRoutes()).toEqual(["a", "b", "c"]);
	});
});

describe("gestures", () => {
	let root: HTMLDivElement;
	let release: () => void;

	beforeEach(() => {
		at("/a", { panes: [pane("a"), pane("b")], focus: 0 });
		root = document.createElement("div");
		document.body.append(root);
		release = catchAnchors(root, paneRule);
	});

	afterEach(() => {
		release();
		root.remove();
	});

	function link(href: string, attrs: Record<string, string> = {}) {
		const a = document.createElement("a");
		a.setAttribute("href", href);
		for (const [k, v] of Object.entries(attrs)) a.setAttribute(k, v);
		root.append(a);
		return a;
	}

	function click(a: HTMLElement, init: MouseEventInit = {}) {
		const e = new MouseEvent("click", { bubbles: true, cancelable: true, ...init });
		a.dispatchEvent(e);
		return e;
	}

	it("opens a plain click in the focused pane", () => {
		const e = click(link("/movie?id=1"));
		expect(e.defaultPrevented).toBe(true);
		expect(currentRoutes()).toEqual(["movie", "b"]);
		expect(url()).toBe("/movie?id=1");
	});

	it("opens an Option click beside", () => {
		const e = click(link("/movie?id=1"), { altKey: true });
		expect(e.defaultPrevented).toBe(true);
		expect(currentRoutes()).toEqual(["a", "movie", "b"]);
	});

	it("opens Option+Enter beside", () => {
		const a = link("/x");
		const e = new KeyboardEvent("keydown", {
			key: "Enter",
			altKey: true,
			bubbles: true,
			cancelable: true,
		});
		a.dispatchEvent(e);
		expect(e.defaultPrevented).toBe(true);
		expect(currentRoutes()).toEqual(["a", "x", "b"]);
	});

	it("opens / as home", () => {
		click(link("/"));
		expect(url()).toBe("/home");
	});

	it("leaves the rest native", () => {
		const cases: [HTMLElement, MouseEventInit][] = [
			[link("/x"), { metaKey: true }],
			[link("/x"), { ctrlKey: true }],
			[link("/x"), { shiftKey: true }],
			[link("/x/y"), {}],
			[link("/x", { target: "_blank" }), {}],
			[link("/x", { download: "" }), {}],
			[link("https://example.com/x"), {}],
		];
		for (const [a, init] of cases) {
			const e = click(a, init);
			expect(e.defaultPrevented).toBe(false);
		}
		expect(currentRoutes()).toEqual(["a", "b"]);
		expect(url()).toBe("/a");
	});
});
