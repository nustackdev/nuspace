// Opening a plane to the side: from a solo plane, a plane
// item, a strip (after the link's pane, or the focused one), an empty desk, a
// plane the strip shows already, and the gesture through the kit's catcher.

import { catchAnchors } from "@nustackdev/ui-kit";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
	currentRoute,
	currentRoutes,
	focusedRoute,
	focusPane,
	itemHref,
	knownDesks,
	resetRouter,
	setDesks,
	setRoles,
} from "../core/router";
import type { Desk, Link, Strip } from "./model";
import { linkRule, openToTheSide } from "./open";

const DESK = "desk0001";
const L = (plane: string, params: Record<string, string> = {}): Link => ({ plane, params });

function strip(id: string, ...planes: string[]): Strip {
	return {
		id,
		kind: "strip",
		columns: planes.map((p) => ({ panes: [{ share: 1, original: L(p) }] })),
	};
}

const usual = (): Desk => ({
	name: "Work",
	items: [{ id: "pitem1", kind: "plane", original: L("a") }, strip("strip1", "b", "c", "d")],
});

function at(path: string) {
	window.history.replaceState(null, "", path);
}

const desk = (id = DESK) => knownDesks()?.[id] as Desk;
const others = () => Object.keys(knownDesks() ?? {}).filter((id) => id !== DESK);

beforeEach(() => {
	resetRouter();
	setRoles({ home: "p_home" });
	setDesks({ [DESK]: usual() });
	at("/");
});

describe("openToTheSide", () => {
	it("makes a new desk of a solo plane and the link, side by side, the link focused", () => {
		at("/p/s?x=1");
		openToTheSide(L("movie", { id: "1" }));
		const [id] = others();
		expect(desk(id).items).toHaveLength(1);
		expect(currentRoutes()).toEqual(["s", "movie"]);
		expect(focusedRoute()).toBe("movie");
		expect(currentRoute()).toMatchObject({ kind: "item", desk: id });
	});

	it("opens the solo plane itself in place, no desk made", () => {
		at("/p/s");
		openToTheSide(L("s", { q: "2" }));
		expect(others()).toEqual([]);
		expect(currentRoute()).toEqual({ kind: "solo", plane: "s", params: { q: "2" } });
	});

	it("makes a plane item a strip, the link to its right", () => {
		at(itemHref(DESK, "pitem1"));
		openToTheSide(L("x"));
		expect(desk().items[0]).toMatchObject({ id: "pitem1", kind: "strip" });
		expect(currentRoutes()).toEqual(["a", "x"]);
		expect(focusedRoute()).toBe("x");
	});

	it("puts the link right of the pane it sits in, else of the focused pane", () => {
		at(itemHref(DESK, "strip1"));
		focusPane(DESK, "strip1", "d");
		openToTheSide(L("x"), "b");
		expect(currentRoutes()).toEqual(["b", "x", "c", "d"]);
		expect(focusedRoute()).toBe("x");
		focusPane(DESK, "strip1", "c");
		openToTheSide(L("y"));
		expect(currentRoutes()).toEqual(["b", "x", "c", "y", "d"]);
		expect(focusedRoute()).toBe("y");
	});

	it("focuses a plane the strip shows already, nothing written", () => {
		at(itemHref(DESK, "strip1"));
		focusPane(DESK, "strip1", "d");
		const before = desk();
		openToTheSide(L("b"), "d");
		expect(desk()).toBe(before);
		expect(focusedRoute()).toBe("b");
	});

	it("pins the link as an empty desk's first item", () => {
		setDesks({ [DESK]: usual(), desk0002: { name: "", items: [] } });
		at("/d/desk0002");
		openToTheSide(L("x"));
		expect(desk("desk0002").items).toMatchObject([{ kind: "plane", original: L("x") }]);
		expect(currentRoutes()).toEqual(["x"]);
	});
});

describe("linkRule", () => {
	let root: HTMLElement;
	let release: () => void;

	beforeEach(() => {
		root = document.createElement("div");
		document.body.append(root);
		release = catchAnchors(root, linkRule);
		at(itemHref(DESK, "strip1"));
		focusPane(DESK, "strip1", "d");
	});

	afterEach(() => {
		release();
		root.remove();
	});

	function click(href: string, init: MouseEventInit, pane = "") {
		const box = document.createElement("div");
		if (pane) box.setAttribute("data-pane", pane);
		const a = document.createElement("a");
		a.setAttribute("href", href);
		box.append(a);
		root.append(box);
		const e = new MouseEvent("click", { bubbles: true, cancelable: true, ...init });
		a.dispatchEvent(e);
		return e;
	}

	it("opens an Option Cmd click to the side of the link's pane", () => {
		expect(click("/p/x", { altKey: true, metaKey: true }, "b").defaultPrevented).toBe(true);
		expect(currentRoutes()).toEqual(["b", "x", "c", "d"]);
	});

	it("leaves a plain or Option click and a desk or item url to the router", () => {
		click("/p/x", { altKey: true }, "b");
		expect(currentRoutes()).toEqual(["x", "c", "d"]);
		expect(others()).toEqual([]);
		click(itemHref(DESK, "pitem1"), { altKey: true, metaKey: true });
		click("/p/y", { altKey: true, metaKey: true, shiftKey: true });
		expect(currentRoutes()).toEqual(["a"]);
		expect(others()).toEqual([]);
	});
});
