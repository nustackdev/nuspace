// The router in jsdom, on the kit's real History: url shapes, landing for
// every row of the url table, navigation inside a desk item writing recent
// (links, a program's push or query), the strip dedupe, focus per tab per
// strip, the desk ops by id, back and forward, and the link gestures.

import { catchAnchors, History } from "@nustackdev/ui-kit";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Desk, Item, Link, Pane, PlaneItem, Strip } from "../desk/model";
import {
	closeColumn,
	closeDesk,
	closeItem,
	closePane,
	createDesk,
	currentRoute,
	currentRoutes,
	deskHref,
	deskName,
	ensureLanding,
	focusedRoute,
	focusPane,
	hrefFor,
	itemHref,
	knownDesks,
	leavePlanes,
	navigate,
	onDeskDelete,
	onDeskWrite,
	onReveal,
	openInNewTab,
	openItem,
	openPane,
	openPlane,
	paneRule,
	paramsOf,
	renameDesk,
	resetItem,
	resetRouter,
	resolve,
	saveItem,
	setDesks,
	setRoles,
	setShares,
	setWidth,
	shapeOf,
	shapeOfHref,
} from "./router";

const DESK = "desk0001";
const OTHER = "desk0002";
const P = "pitem1";
const S = "strip1";

const L = (plane: string, params: Record<string, string> = {}): Link => ({ plane, params });

function pi(id: string, plane: string, recent?: Link): PlaneItem {
	return recent
		? { id, kind: "plane", original: L(plane), recent }
		: { id, kind: "plane", original: L(plane) };
}

function pn(plane: string, recent?: Link): Pane {
	return recent ? { share: 1, original: L(plane), recent } : { share: 1, original: L(plane) };
}

/** A strip of one column per plane. */
function st(id: string, ...planes: (string | Pane)[]): Strip {
	return {
		id,
		kind: "strip",
		columns: planes.map((p) => ({ panes: [typeof p === "string" ? pn(p) : p] })),
	};
}

function dk(name: string, ...items: Item[]): Desk {
	return { name, items };
}

/** The usual desk: a plane item `a`, then a strip of `b` and `c`. */
const usual = () => dk("Work", pi(P, "a"), st(S, "b", "c"));

function at(path: string) {
	window.history.replaceState(null, "", path);
}

const url = () => window.location.pathname + window.location.search;

/** Desks and roles landed. */
function known(desks: Record<string, Desk>) {
	setRoles({ home: "p_home" });
	setDesks(desks);
}

/** The next History move, once it lands (back and forward land later). */
function nextMove(): Promise<void> {
	return new Promise((resolve) => {
		const off = History.subscribe(() => {
			off();
			resolve();
		});
	});
}

const tick = () => Promise.resolve();

const desk = (id = DESK) => knownDesks()?.[id] as Desk;

beforeEach(() => {
	resetRouter();
	at("/");
});

describe("url shapes", () => {
	it("tells root, desk, item, plane and nothing apart by prefix", () => {
		expect(shapeOf("/")).toEqual({ kind: "root" });
		expect(shapeOf("/d/ab12cd34")).toEqual({ kind: "desk", desk: "ab12cd34" });
		expect(shapeOf("/d/ab12cd34/k3x9ab")).toEqual({
			kind: "item",
			desk: "ab12cd34",
			item: "k3x9ab",
		});
		expect(shapeOf("/p/p_0190_0001_ab12")).toEqual({ kind: "plane", plane: "p_0190_0001_ab12" });
		// A desk shaped plane id is a plane: the prefix says so.
		expect(shapeOf("/p/settings")).toEqual({ kind: "plane", plane: "settings" });
		// A plane id is key chars only.
		expect(shapeOf("/p/a%20b")).toEqual({ kind: "none" });
		expect(shapeOf("/d/ab12cd34/K3X9AB")).toEqual({ kind: "none" });
		expect(shapeOf("/d/x/k3x9ab")).toEqual({ kind: "none" });
		expect(shapeOf("/d/ab12cd34/k3x9ab/x")).toEqual({ kind: "none" });
		expect(shapeOf("/p/a/b")).toEqual({ kind: "none" });
		expect(shapeOf("/p/")).toEqual({ kind: "none" });
		expect(shapeOf("/p")).toEqual({ kind: "none" });
		expect(shapeOf("/p/%E0%A4%A")).toEqual({ kind: "none" });
		// No prefix: the old forms are nothing.
		expect(shapeOf("/ab12cd34")).toEqual({ kind: "none" });
		expect(shapeOf("/ab12cd34/k3x9ab")).toEqual({ kind: "none" });
		expect(shapeOf("/p_0190_0001_ab12")).toEqual({ kind: "none" });
		expect(shapeOf("/x/settings")).toEqual({ kind: "none" });
	});

	it("reads an href, leaving a hash or a deeper path out", () => {
		expect(shapeOfHref("/p/movie?id=42")).toEqual({
			shape: { kind: "plane", plane: "movie" },
			params: { id: "42" },
		});
		expect(shapeOfHref(`/d/${DESK}/${P}`)?.shape).toEqual({ kind: "item", desk: DESK, item: P });
		expect(shapeOfHref("/p/x#top")).toBeNull();
		expect(shapeOfHref("/p/x/y")).toBeNull();
		expect(shapeOfHref("/x")).toBeNull();
	});

	it("builds urls", () => {
		expect(hrefFor("a b", { k: "v" })).toBe("/p/a%20b?k=v");
		expect(deskHref(DESK)).toBe(`/d/${DESK}`);
		expect(itemHref(DESK, P)).toBe(`/d/${DESK}/${P}`);
	});

	it("shows a plane url at once, / once the roles land, a desk url once the desks do", () => {
		const desks = { [DESK]: usual(), [OTHER]: dk("Empty") };
		const e = (path: string, query = {}) => ({ path, query });
		expect(resolve(e("/p/m"), null, null)).toEqual({ kind: "solo", plane: "m", params: {} });
		expect(resolve(e("/"), desks, null)).toEqual({ kind: "pending" });
		expect(resolve(e(`/d/${DESK}`), null, { home: "h" })).toEqual({ kind: "pending" });
		expect(resolve(e(`/d/${DESK}/${P}`), null, { home: "h" })).toEqual({ kind: "pending" });
		const roles = { home: "h" };
		expect(resolve(e("/"), null, roles)).toEqual({ kind: "solo", plane: "h", params: {} });
		expect(resolve(e("/"), desks, {})).toEqual({ kind: "missing", what: "page", id: "/" });
		expect(resolve(e("/p/m", { id: "1" }), desks, roles)).toEqual({
			kind: "solo",
			plane: "m",
			params: { id: "1" },
		});
		expect(resolve(e(`/d/${DESK}/${S}`), desks, roles)).toMatchObject({
			kind: "item",
			desk: DESK,
			name: "Work",
			focus: "b",
		});
		expect(resolve(e(`/d/${DESK}`), desks, roles)).toMatchObject({
			kind: "item",
			desk: DESK,
			item: { id: P },
		});
		expect(resolve(e(`/d/${OTHER}`), desks, roles)).toEqual({
			kind: "desk",
			desk: OTHER,
			name: "Empty",
		});
		expect(resolve(e("/d/zzzzzzzz"), desks, roles)).toEqual({
			kind: "missing",
			what: "desk",
			id: "zzzzzzzz",
		});
		expect(resolve(e(`/d/zzzzzzzz/${P}`), desks, roles)).toEqual({
			kind: "missing",
			what: "desk",
			id: "zzzzzzzz",
		});
		expect(resolve(e(`/d/${DESK}/zzzzzz`), desks, roles)).toEqual({
			kind: "missing",
			what: "item",
			id: "Work / zzzzzz",
		});
		expect(resolve(e("/a/b/c"), desks, roles)).toEqual({
			kind: "missing",
			what: "page",
			id: "/a/b/c",
		});
	});

	it("takes only segments of an id's shape, a page not found for anything else", () => {
		const desks = { [DESK]: usual() };
		const roles = { home: "h" };
		const e = (path: string) => ({ path, query: {} });
		const page = (path: string) => ({ kind: "missing", what: "page", id: path });
		// Plane ids: key chars, minted, a system plane's name, an id given in code.
		for (const ok of ["/p/p_01a1cb96cbab_0006_3f2d", "/p/home_indexer", "/p/My-plane_2"]) {
			expect(resolve(e(ok), desks, roles).kind).toBe("solo");
		}
		for (const bad of ["/p/a%20b", "/p/a.b", "/p/%E2%9C%93", `/p/${"x".repeat(129)}`]) {
			expect(resolve(e(bad), desks, roles)).toEqual(page(bad));
		}
		// A desk id (8) and an item id (6), nothing else.
		for (const bad of [
			`/d/${DESK}/abc`,
			`/d/${DESK}/ABCDEF`,
			`/d/short/${P}`,
			`/d/${DESK}/${P}x`,
			"/d/short",
		]) {
			expect(resolve(e(bad), desks, roles)).toEqual(page(bad));
		}
		// Old urls, no prefix: a page not found, no redirect.
		for (const bad of [`/${DESK}`, `/${DESK}/${P}`, "/home_indexer", "/zzzzzzzz"]) {
			expect(resolve(e(bad), desks, roles)).toEqual(page(bad));
		}
	});
});

describe("landing: the url table", () => {
	it("replaces / with home's plane url once desks and roles land", async () => {
		ensureLanding();
		expect(currentRoute()).toEqual({ kind: "pending" });
		const before = window.history.length;
		known({});
		await tick();
		expect(url()).toBe("/p/p_home");
		expect(window.history.length).toBe(before);
		expect(focusedRoute()).toBe("p_home");
	});

	it("shows /<plane id> solo, its query as params", () => {
		known({});
		at("/p/movie?id=42");
		expect(currentRoute()).toEqual({ kind: "solo", plane: "movie", params: { id: "42" } });
		expect(currentRoutes()).toEqual(["movie"]);
		expect(paramsOf("movie")).toEqual({ id: "42" });
		expect(deskName()).toBe("");
	});

	it("shows /<desk id>/<item id>: a plane item, a strip", () => {
		known({ [DESK]: usual() });
		at(itemHref(DESK, P));
		expect(currentRoute()).toMatchObject({ kind: "item", desk: DESK, name: "Work", focus: "a" });
		expect(currentRoutes()).toEqual(["a"]);
		at(itemHref(DESK, S));
		expect(currentRoutes()).toEqual(["b", "c"]);
		expect(focusedRoute()).toBe("b");
		expect(deskName()).toBe("Work");
	});

	it("replaces /<desk id> with its first item's url", async () => {
		known({ [DESK]: usual() });
		at(deskHref(DESK));
		ensureLanding();
		await tick();
		expect(url()).toBe(itemHref(DESK, P));
	});

	it("keeps /<desk id> of an empty desk as the empty desk state", async () => {
		known({ [DESK]: dk("Empty") });
		at(deskHref(DESK));
		ensureLanding();
		await tick();
		expect(url()).toBe(deskHref(DESK));
		expect(currentRoute()).toEqual({ kind: "desk", desk: DESK, name: "Empty" });
		expect(currentRoutes()).toEqual([]);
		expect(deskName()).toBe("Empty");
	});

	it("keeps an unknown desk's url and says the desk is not found", async () => {
		known({ [DESK]: usual() });
		at(`/d/zzzzzzzz/${P}`);
		ensureLanding();
		await tick();
		expect(url()).toBe(`/d/zzzzzzzz/${P}`);
		expect(currentRoute()).toEqual({ kind: "missing", what: "desk", id: "zzzzzzzz" });
	});

	it("keeps a known desk's unknown item url and says the item is not found", async () => {
		known({ [DESK]: usual() });
		at(`/d/${DESK}/zzzzzz`);
		ensureLanding();
		await tick();
		await tick();
		expect(url()).toBe(`/d/${DESK}/zzzzzz`);
		expect(currentRoute()).toMatchObject({ kind: "missing", what: "item" });
	});

	it("shows a desk shaped plane id solo before anything lands", () => {
		at("/p/settings?tab=keys");
		expect(currentRoute()).toEqual({ kind: "solo", plane: "settings", params: { tab: "keys" } });
	});

	it("drops a query off an item url", async () => {
		known({ [DESK]: usual() });
		at(`${itemHref(DESK, P)}?x=1`);
		ensureLanding();
		await tick();
		expect(url()).toBe(itemHref(DESK, P));
	});

	it("an item closed elsewhere sends the tab to the desk's first item", async () => {
		known({ [DESK]: usual() });
		at(itemHref(DESK, S));
		ensureLanding();
		setDesks({ [DESK]: dk("Work", pi(P, "a")) });
		await tick();
		await tick();
		expect(url()).toBe(itemHref(DESK, P));
	});

	it("a desk closed elsewhere sends the tab home", async () => {
		known({ [DESK]: usual() });
		at(itemHref(DESK, P));
		ensureLanding();
		setDesks({});
		await tick();
		expect(url()).toBe("/p/p_home");
	});
});

describe("navigation inside a desk item", () => {
	beforeEach(() => known({ [DESK]: usual() }));

	it("writes a plane item's recent, the url kept, one desk write", () => {
		const wrote = vi.fn();
		onDeskWrite(wrote);
		at(itemHref(DESK, P));
		navigate(L("x", { run: "43" }));
		expect(url()).toBe(itemHref(DESK, P));
		expect(desk().items[0]).toEqual(pi(P, "a", L("x", { run: "43" })));
		expect(currentRoutes()).toEqual(["x"]);
		expect(paramsOf("x")).toEqual({ run: "43" });
		expect(wrote).toHaveBeenCalledTimes(1);
		navigate(L("a"));
		expect(desk().items[0]).toEqual(pi(P, "a"));
	});

	it("writes the focused pane's recent in a strip, or the pane named", () => {
		at(itemHref(DESK, S));
		focusPane(DESK, S, "c");
		navigate(L("x"));
		expect((desk().items[1] as Strip).columns[1].panes[0]).toEqual(pn("c", L("x")));
		expect(focusedRoute()).toBe("x");
		navigate(L("y"), "b");
		expect((desk().items[1] as Strip).columns[0].panes[0]).toEqual(pn("b", L("y")));
		expect(focusedRoute()).toBe("y");
		expect(currentRoutes()).toEqual(["y", "x"]);
	});

	it("focuses the pane that shows the plane already, nothing written, and brings it on screen", () => {
		const wrote = vi.fn();
		const shown = vi.fn();
		onDeskWrite(wrote);
		onReveal(shown);
		at(itemHref(DESK, S));
		navigate(L("c"), "b");
		expect(wrote).not.toHaveBeenCalled();
		expect(focusedRoute()).toBe("c");
		expect(shown).toHaveBeenCalledWith("c");
	});

	it("just navigates in a solo plane", () => {
		at("/p/s");
		navigate(L("m", { k: "1" }));
		expect(url()).toBe("/p/m?k=1");
		expect(desk()).toEqual(usual());
	});

	it("reads a program's push to a plane url as navigation, the item url put back", async () => {
		at(itemHref(DESK, P));
		ensureLanding();
		History.push("/p/x?k=1");
		expect(currentRoute()).toMatchObject({ kind: "item", desk: DESK });
		await tick();
		expect(url()).toBe(itemHref(DESK, P));
		expect(desk().items[0]).toEqual(pi(P, "a", L("x", { k: "1" })));
	});

	it("reads a program's query on an item url as the focused pane's params", async () => {
		at(itemHref(DESK, S));
		ensureLanding();
		focusPane(DESK, S, "c");
		History.push(`${itemHref(DESK, S)}?k=2`);
		await tick();
		expect(url()).toBe(itemHref(DESK, S));
		expect((desk().items[1] as Strip).columns[1].panes[0]).toEqual(pn("c", L("c", { k: "2" })));
	});

	it("leaves a removed solo plane for home, and a desk item as it is", () => {
		at("/p/gone");
		leavePlanes(["gone"], true);
		expect(url()).toBe("/p/p_home");
		at(itemHref(DESK, P));
		leavePlanes(["a"]);
		expect(url()).toBe(itemHref(DESK, P));
	});

	it("opens a plane in a new tab with the params it is shown with", () => {
		const open = vi.spyOn(window, "open").mockReturnValue(null);
		desk().items[0] = pi(P, "a", L("a", { k: "v" }));
		at(itemHref(DESK, P));
		openInNewTab("a");
		expect(open).toHaveBeenCalledWith("/p/a?k=v", "_blank", "noopener");
		open.mockRestore();
	});
});

describe("desk ops by id", () => {
	beforeEach(() => known({ [DESK]: usual() }));

	it("creates an empty desk named Untitled, returning its id", () => {
		const wrote = vi.fn();
		onDeskWrite(wrote);
		const id = createDesk();
		expect(id).toMatch(/^[a-z0-9]{8}$/);
		expect(desk(id)).toEqual({ name: "Untitled", items: [] });
		expect(wrote).toHaveBeenCalledWith(id, { name: "Untitled", items: [] });
	});

	it("renames a desk", () => {
		renameDesk(DESK, "Play");
		expect(desk().name).toBe("Play");
	});

	it("closes a desk: gone, the delete hook told, a tab on it home", () => {
		const deleted: string[] = [];
		onDeskDelete((id) => deleted.push(id));
		at(itemHref(DESK, S));
		closeDesk(DESK);
		expect(knownDesks()).toEqual({});
		expect(deleted).toEqual([DESK]);
		expect(url()).toBe("/p/p_home");
	});

	it("closing another desk leaves the tab be", () => {
		known({ [DESK]: usual(), [OTHER]: dk("Other") });
		at(itemHref(DESK, P));
		closeDesk(OTHER);
		expect(url()).toBe(itemHref(DESK, P));
	});

	it("saves and resets", () => {
		at(itemHref(DESK, P));
		navigate(L("x"));
		saveItem(DESK, P);
		expect(desk().items[0]).toEqual(pi(P, "x"));
		navigate(L("y"));
		resetItem(DESK, P);
		expect(desk().items[0]).toEqual(pi(P, "x"));
	});

	it("reset in a strip focuses the pane already showing the original", () => {
		known({ [DESK]: dk("Work", st(S, pn("b", L("x")), pn("q", L("b")))) });
		at(itemHref(DESK, S));
		resetItem(DESK, S, "x");
		expect(focusedRoute()).toBe("b");
		expect((desk().items[0] as Strip).columns[0].panes[0]).toEqual(pn("b", L("x")));
	});

	it("opens an item (pushed), and a strip focusing a pane", () => {
		const shown = vi.fn();
		onReveal(shown);
		at("/p/s");
		const before = window.history.length;
		openItem(DESK, P);
		expect(url()).toBe(itemHref(DESK, P));
		expect(window.history.length).toBe(before + 1);
		openItem(DESK, P);
		expect(window.history.length).toBe(before + 1);
		openPane(DESK, S, "c");
		expect(url()).toBe(itemHref(DESK, S));
		expect(focusedRoute()).toBe("c");
		expect(shown).toHaveBeenCalledWith("c");
	});

	it("closes an item, a pane, a column; a strip of one becomes a plane item", () => {
		closePane(DESK, S, "c");
		expect(desk().items[1]).toEqual(pi(S, "b"));
		known({ [DESK]: dk("Work", pi(P, "a"), st(S, "b", "c", "d")) });
		closeColumn(DESK, S, 0);
		expect((desk().items[1] as Strip).columns).toHaveLength(2);
		closeItem(DESK, P);
		expect(desk().items.map((i) => i.id)).toEqual([S]);
	});

	it("resizes columns and sets shares", () => {
		setWidth(DESK, S, "c", 700);
		expect((desk().items[1] as Strip).columns[1].width).toBe(700);
		known({
			[DESK]: dk("Work", {
				id: S,
				kind: "strip",
				columns: [
					{
						panes: [
							{ share: 0.5, original: L("b") },
							{ share: 0.5, original: L("c") },
						],
					},
				],
			}),
		});
		setShares(DESK, S, "b", [1, 3]);
		expect((desk().items[0] as Strip).columns[0].panes.map((p) => p.share)).toEqual([0.25, 0.75]);
	});

	it("does nothing on an unknown desk", () => {
		const wrote = vi.fn();
		onDeskWrite(wrote);
		renameDesk(OTHER, "x");
		closeItem(OTHER, P);
		saveItem(OTHER, P);
		expect(wrote).not.toHaveBeenCalled();
	});
});

describe("focus and history", () => {
	it("keeps focus per strip, this tab only, through back and forward", async () => {
		known({ [DESK]: usual(), [OTHER]: dk("Other", st(S, "x", "y")) });
		at("/p/s");
		openItem(DESK, S);
		focusPane(DESK, S, "c");
		openItem(OTHER, S);
		expect(focusedRoute()).toBe("x");
		const back = nextMove();
		History.back();
		await back;
		expect(currentRoute()).toMatchObject({ kind: "item", desk: DESK, focus: "c" });
		const again = nextMove();
		History.back();
		await again;
		expect(currentRoute()).toEqual({ kind: "solo", plane: "s", params: {} });
	});

	it("ignores focus on a plane the strip does not show", () => {
		known({ [DESK]: usual() });
		at(itemHref(DESK, S));
		focusPane(DESK, S, "zz");
		expect(focusedRoute()).toBe("b");
	});

	it("opens a plane solo, pushed", () => {
		known({ [DESK]: usual() });
		at(itemHref(DESK, P));
		openPlane("m");
		expect(url()).toBe("/p/m");
		expect(desk()).toEqual(usual());
	});
});

describe("gestures", () => {
	let root: HTMLDivElement;
	let release: () => void;

	beforeEach(() => {
		known({ [DESK]: usual() });
		at(itemHref(DESK, S));
		root = document.createElement("div");
		document.body.append(root);
		release = catchAnchors(root, paneRule);
	});

	afterEach(() => {
		release();
		root.remove();
	});

	function link(href: string, attrs: Record<string, string> = {}, inside: HTMLElement = root) {
		const a = document.createElement("a");
		a.setAttribute("href", href);
		for (const [k, v] of Object.entries(attrs)) a.setAttribute(k, v);
		inside.append(a);
		return a;
	}

	function click(a: HTMLElement, init: MouseEventInit = {}) {
		const e = new MouseEvent("click", { bubbles: true, cancelable: true, ...init });
		a.dispatchEvent(e);
		return e;
	}

	it("navigates the pane holding the link in place", () => {
		const pane = document.createElement("div");
		pane.setAttribute("data-pane", "c");
		root.append(pane);
		const e = click(link("/p/movie?id=1", {}, pane));
		expect(e.defaultPrevented).toBe(true);
		expect(url()).toBe(itemHref(DESK, S));
		expect(currentRoutes()).toEqual(["b", "movie"]);
	});

	it("opens a plane url outside any pane solo, on a desk item too", () => {
		const writes = vi.fn();
		const off = onDeskWrite(writes);
		const e = click(link("/p/movie?id=1"));
		expect(e.defaultPrevented).toBe(true);
		expect(url()).toBe("/p/movie?id=1");
		expect(currentRoute()).toEqual({ kind: "solo", plane: "movie", params: { id: "1" } });
		expect(desk().items[1]).toEqual(st(S, "b", "c"));
		expect(writes).not.toHaveBeenCalled();
		off();
	});

	it("opens / outside any pane as home's plane, solo", () => {
		click(link("/"));
		expect(url()).toBe("/p/p_home");
	});

	it("opens an item url as that item, from a pane too", () => {
		const pane = document.createElement("div");
		pane.setAttribute("data-pane", "b");
		root.append(pane);
		click(link(itemHref(DESK, P), {}, pane));
		expect(url()).toBe(itemHref(DESK, P));
		expect(currentRoutes()).toEqual(["a"]);
		expect(desk().items[1]).toEqual(st(S, "b", "c"));
	});

	it("pushes a plane url in a solo plane", () => {
		at("/p/s");
		click(link("/p/movie?id=1"));
		expect(url()).toBe("/p/movie?id=1");
	});

	it("opens a desk or item url, and / as home", () => {
		click(link(itemHref(DESK, P)));
		expect(url()).toBe(itemHref(DESK, P));
		at("/p/s");
		click(link("/"));
		expect(url()).toBe("/p/p_home");
		click(link(deskHref(DESK)));
		expect(url()).toBe(deskHref(DESK));
	});

	it("leaves the rest native", () => {
		const cases: [HTMLElement, MouseEventInit][] = [
			[link("/p/x"), { metaKey: true }],
			[link("/p/x"), { ctrlKey: true }],
			[link("/p/x"), { shiftKey: true }],
			[link("/p/x/y/z"), {}],
			[link("/p/x#top"), {}],
			[link("/p/x", { target: "_blank" }), {}],
			[link("https://example.com/x"), {}],
		];
		for (const [a, init] of cases) expect(click(a, init).defaultPrevented).toBe(false);
		expect(currentRoutes()).toEqual(["b", "c"]);
		expect(url()).toBe(itemHref(DESK, S));
	});
});
