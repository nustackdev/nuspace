// The router in jsdom: "/" is the one path override, and lands on /home.
// Pane moves (a drop on the panes, a tab drag) and which clicks it leaves to
// the browser.

import type * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
	closePanes,
	currentRoutes,
	ensureLanding,
	hrefFor,
	movePane,
	onNavClick,
	openInNewTab,
	openPaneAt,
	redirected,
	replacePane,
	routeAnchorClick,
	routesOfHref,
	splitRoutes,
} from "./router";

function at(path: string) {
	window.history.replaceState({}, "", path);
}

describe("router", () => {
	beforeEach(() => at("/"));

	it("routes home like any plane", () => {
		expect(hrefFor("home")).toBe("/home");
		expect(splitRoutes("/home")).toEqual(["home"]);
		expect(hrefFor("settings")).toBe("/settings");
		expect(splitRoutes("/settings")).toEqual(["settings"]);
	});

	it("names no plane at /", () => {
		expect(hrefFor([])).toBe("/");
		expect(splitRoutes("/")).toEqual([]);
		expect(splitRoutes("/a/b")).toEqual([]);
		expect(routesOfHref("/")).toEqual([]);
	});

	it("redirects / and nothing else", () => {
		expect(redirected("/")).toBe("/home");
		expect(redirected("/home")).toBe("/home");
		expect(redirected("/a+b")).toBe("/a+b");
	});

	it("lands / on /home, replacing the entry", () => {
		const before = window.history.length;
		ensureLanding();
		expect(window.location.pathname).toBe("/home");
		expect(window.history.length).toBe(before);
		at("/a/b");
		ensureLanding();
		expect(window.location.pathname).toBe("/home");
		at("/a+a");
		ensureLanding();
		expect(window.location.pathname).toBe("/a");
	});

	it("closing the last pane lands home", () => {
		at("/home");
		replacePane("p1");
		expect(window.location.pathname).toBe("/p1");
		closePanes(["p1"], true);
		expect(window.location.pathname).toBe("/home");
		expect(currentRoutes()).toEqual(["home"]);
	});

	it("opens a dropped plane at an index, and only focuses one already open", () => {
		at("/a+b");
		openPaneAt("c", 1);
		expect(currentRoutes()).toEqual(["a", "c", "b"]);
		openPaneAt("d", 0);
		expect(currentRoutes()).toEqual(["d", "a", "c", "b"]);
		openPaneAt("e", 99);
		expect(currentRoutes()).toEqual(["d", "a", "c", "b", "e"]);
		const before = window.history.length;
		openPaneAt("a", 0);
		expect(currentRoutes()).toEqual(["d", "a", "c", "b", "e"]);
		expect(window.history.length).toBe(before);
	});

	it("moves a pane to an index counted without it", () => {
		at("/a+b+c");
		movePane("a", 2);
		expect(currentRoutes()).toEqual(["b", "c", "a"]);
		movePane("a", 0);
		expect(currentRoutes()).toEqual(["a", "b", "c"]);
		movePane("x", 0);
		expect(currentRoutes()).toEqual(["a", "b", "c"]);
	});

	it("opens a plane in a new browser tab on its own URL", () => {
		const open = vi.spyOn(window, "open").mockReturnValue(null);
		openInNewTab("a b");
		expect(open).toHaveBeenCalledWith("/a%20b", "_blank", "noopener");
		open.mockRestore();
	});
});

describe("clicks", () => {
	beforeEach(() => at("/a"));

	const click = (init: MouseEventInit) =>
		({
			button: 0,
			preventDefault: vi.fn(),
			defaultPrevented: false,
			...init,
		}) as unknown as React.MouseEvent<HTMLElement> & { preventDefault: ReturnType<typeof vi.fn> };

	it("routes a plain click and leaves a modified one to the browser", () => {
		const plain = click({});
		onNavClick("b")(plain);
		expect(plain.preventDefault).toHaveBeenCalled();
		expect(currentRoutes()).toEqual(["b"]);
		for (const init of [
			{ metaKey: true },
			{ ctrlKey: true },
			{ shiftKey: true },
			{ altKey: true },
			{ button: 1 },
		]) {
			const e = click(init);
			onNavClick("c")(e);
			expect(e.preventDefault).not.toHaveBeenCalled();
		}
		expect(currentRoutes()).toEqual(["b"]);
	});

	it("leaves a cmd/ctrl-click on a link in a cell to the browser", () => {
		const a = document.createElement("a");
		a.href = "/b";
		document.body.append(a);
		for (const init of [{ metaKey: true }, { ctrlKey: true }]) {
			const e = new MouseEvent("click", { bubbles: true, cancelable: true, ...init });
			Object.defineProperty(e, "target", { value: a });
			expect(routeAnchorClick(e)).toBe(false);
			expect(e.defaultPrevented).toBe(false);
		}
		const plain = new MouseEvent("click", { bubbles: true, cancelable: true });
		Object.defineProperty(plain, "target", { value: a });
		expect(routeAnchorClick(plain)).toBe(true);
		expect(currentRoutes()).toEqual(["b"]);
		a.remove();
	});
});
