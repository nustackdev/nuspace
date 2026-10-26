// The layout model, pure: an entry read as a layout, the URL a layout lives
// at, the hrefs that are panes, and every move.

import { describe, expect, it } from "vitest";
import {
	close,
	focus,
	homeLayout,
	hrefOf,
	type Layout,
	layoutOf,
	move,
	openAt,
	openBeside,
	openHere,
	planeOfPath,
	stateLayout,
	targetOfHref,
	urlOf,
} from "./layout";

const pane = (plane: string, params: Record<string, string> = {}) => ({ plane, params });
const desk = (focusAt: number, ...panes: ReturnType<typeof pane>[]): Layout => ({
	panes,
	focus: focusAt,
});
const entry = (path: string, query: Record<string, string> = {}, state: unknown = null) => ({
	path,
	query,
	state,
});

describe("urls", () => {
	it("names one plane per URL, the focused pane's", () => {
		expect(hrefOf(pane("movie", { id: "42" }))).toBe("/movie?id=42");
		expect(hrefOf(pane("a b"))).toBe("/a%20b");
		expect(hrefOf(pane("q", { q: "a b&c" }))).toBe("/q?q=a+b%26c");
		expect(urlOf(desk(1, pane("movies"), pane("movie", { id: "7" })))).toBe("/movie?id=7");
		expect(urlOf({ panes: [], focus: 0 })).toBe("/");
	});

	it("reads one path segment as a plane", () => {
		expect(planeOfPath("/home")).toBe("home");
		expect(planeOfPath("/a%20b")).toBe("a b");
		expect(planeOfPath("/")).toBeNull();
		expect(planeOfPath("/a/b")).toBeNull();
		expect(planeOfPath("/%E0%A4%A")).toBeNull();
	});

	it("tells a pane href from the rest", () => {
		expect(targetOfHref("/movie?id=42")).toEqual(pane("movie", { id: "42" }));
		expect(targetOfHref("/")).toEqual(pane("home"));
		expect(targetOfHref("/a+b")).toEqual(pane("a+b"));
		expect(targetOfHref("/a/b")).toBeNull();
		expect(targetOfHref("/a#x")).toBeNull();
	});
});

describe("reading an entry", () => {
	it("is one pane with its query when the state holds no layout", () => {
		expect(layoutOf(entry("/movie", { id: "42" }))).toEqual(desk(0, pane("movie", { id: "42" })));
		expect(layoutOf(entry("/movie", {}, { junk: true }))).toEqual(desk(0, pane("movie")));
	});

	it("is home when the URL names no plane", () => {
		expect(layoutOf(entry("/"))).toEqual(homeLayout());
		expect(layoutOf(entry("/a/b", {}, desk(0, pane("a"))))).toEqual(homeLayout());
	});

	it("is the state's layout, the URL's pane focused on the URL's query", () => {
		const state = desk(0, pane("movies"), pane("movie", { id: "1" }));
		expect(layoutOf(entry("/movie", { id: "2" }, state))).toEqual(
			desk(1, pane("movies"), pane("movie", { id: "2" })),
		);
		// A URL naming a plane the state does not hold wins: one pane.
		expect(layoutOf(entry("/other", {}, state))).toEqual(desk(0, pane("other")));
	});

	it("reads a state defensively", () => {
		expect(stateLayout(null)).toBeNull();
		expect(stateLayout({ panes: [] })).toBeNull();
		expect(
			stateLayout({
				panes: [{ plane: "a", params: { k: "v", n: 1 } }, { plane: "a" }, { plane: "" }, null],
				focus: 9,
			}),
		).toEqual(desk(0, pane("a", { k: "v" })));
	});

	it("round-trips a layout through its URL and state", () => {
		const layout = desk(1, pane("a"), pane("movie", { id: "42" }), pane("c"));
		const url = new URL(urlOf(layout), "http://x");
		const query = Object.fromEntries(url.searchParams);
		expect(layoutOf(entry(url.pathname, query, structuredClone(layout)))).toEqual(layout);
	});
});

describe("moves", () => {
	const abc = desk(1, pane("a"), pane("b"), pane("c"));

	it("opens here in the focused pane", () => {
		expect(openHere(abc, pane("x", { k: "v" }))).toEqual(
			desk(1, pane("a"), pane("x", { k: "v" }), pane("c")),
		);
		expect(openHere({ panes: [], focus: 0 }, pane("x"))).toEqual(desk(0, pane("x")));
	});

	it("opens beside, right after the focused pane, focused", () => {
		expect(openBeside(abc, pane("x"))).toEqual(desk(2, pane("a"), pane("b"), pane("x"), pane("c")));
	});

	it("moves to a plane already open, with the link's params", () => {
		const moved = desk(2, pane("a"), pane("b"), pane("c", { id: "1" }));
		expect(openHere(abc, pane("c", { id: "1" }))).toEqual(moved);
		expect(openBeside(abc, pane("c", { id: "1" }))).toEqual(moved);
	});

	it("opens a drop at an index, and only focuses one already open", () => {
		expect(openAt(abc, pane("x"), 0)).toEqual(desk(0, pane("x"), pane("a"), pane("b"), pane("c")));
		expect(openAt(abc, pane("x"), 99).panes.at(-1)).toEqual(pane("x"));
		const held = desk(0, pane("a", { k: "v" }), pane("b"));
		expect(openAt(held, pane("a"), 1)).toEqual(held);
	});

	it("closes, focus going left, the last one landing home", () => {
		expect(close(abc, ["b"])).toEqual(desk(0, pane("a"), pane("c")));
		expect(close(desk(0, pane("a"), pane("b")), ["a"])).toEqual(desk(0, pane("b")));
		expect(close(desk(2, pane("a"), pane("b"), pane("c")), ["a"])).toEqual(
			desk(1, pane("b"), pane("c")),
		);
		expect(close(desk(0, pane("a")), ["a"])).toEqual(homeLayout());
		expect(close(abc, ["x"])).toBe(abc);
	});

	it("moves a pane to an index counted without it, focused", () => {
		expect(move(abc, "a", 2)).toEqual(desk(2, pane("b"), pane("c"), pane("a")));
		expect(move(abc, "c", 0)).toEqual(desk(0, pane("c"), pane("a"), pane("b")));
		expect(move(abc, "x", 0)).toBe(abc);
	});

	it("focuses a pane, nothing else", () => {
		expect(focus(abc, 2)).toEqual({ panes: abc.panes, focus: 2 });
		expect(focus(abc, 5)).toBe(abc);
	});

});
