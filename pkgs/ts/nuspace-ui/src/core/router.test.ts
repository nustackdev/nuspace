// The router in jsdom: "/" is the one path override, and lands on /home.

import { beforeEach, describe, expect, it } from "vitest";
import {
	closePanes,
	currentRoutes,
	ensureLanding,
	hrefFor,
	redirected,
	replacePane,
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
});
