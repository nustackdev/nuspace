// The sidebar's rule in jsdom, on the kit's real History: a pane row opens its
// strip with that pane focused, and every other row is the shell's rule (a
// plane url solo even on a desk item, an item url as that item).

import { catchAnchors } from "@nustackdev/ui-kit";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
	currentRoute,
	focusedRoute,
	itemHref,
	knownDesks,
	onReveal,
	resetRouter,
	setDesks,
	setRoles,
} from "../core/router";
import type { Desk } from "../desk/model";
import { PANE_ATTR, RESET_ATTR, resetAttr, sidebarRule } from "./links";

const DESK = "desk0001";
const P = "pitem1";
const S = "strip1";

const L = (plane: string) => ({ plane, params: {} });

const WORK: Desk = {
	name: "Work",
	items: [
		{ id: P, kind: "plane", original: L("a") },
		{
			id: S,
			kind: "strip",
			columns: ["b", "c"].map((p) => ({ panes: [{ share: 1, original: L(p) }] })),
		},
	],
};

const url = () => window.location.pathname + window.location.search;

describe("sidebar links", () => {
	let root: HTMLDivElement;
	let release: () => void;

	beforeEach(() => {
		resetRouter();
		setRoles({ home: "p_home" });
		setDesks({ [DESK]: WORK });
		window.history.replaceState(null, "", itemHref(DESK, P));
		root = document.createElement("div");
		document.body.append(root);
		release = catchAnchors(root, sidebarRule);
	});

	afterEach(() => {
		release();
		root.remove();
	});

	function row(href: string, pane?: string) {
		const li = document.createElement("div");
		if (pane) li.setAttribute(PANE_ATTR, pane);
		const a = document.createElement("a");
		a.setAttribute("href", href);
		li.append(a);
		root.append(li);
		return a;
	}

	it("opens a pane row's strip with that pane focused and on screen", () => {
		const revealed: string[] = [];
		const off = onReveal((plane) => revealed.push(plane));
		row(itemHref(DESK, S), "c").click();
		off();
		expect(url()).toBe(itemHref(DESK, S));
		expect(focusedRoute()).toBe("c");
		expect(revealed).toEqual(["c"]);
	});

	it("resets a navigated item on a plain click of its icon link, in place", () => {
		setDesks({
			[DESK]: {
				...WORK,
				items: [{ id: P, kind: "plane", original: L("a"), recent: L("z") }, WORK.items[1]],
			},
		});
		const icon = row("/p/a");
		icon.setAttribute(RESET_ATTR, resetAttr(DESK, P));
		icon.click();
		expect(url()).toBe(itemHref(DESK, P));
		expect(knownDesks()?.[DESK]?.items[0]).toEqual({ id: P, kind: "plane", original: L("a") });
	});

	it("leaves a Cmd click on the icon link to the browser", () => {
		const icon = row("/p/a");
		icon.setAttribute(RESET_ATTR, resetAttr(DESK, P));
		const e = new MouseEvent("click", { bubbles: true, cancelable: true, metaKey: true });
		icon.dispatchEvent(e);
		expect(e.defaultPrevented).toBe(false);
	});

	it("opens an item row as that item", () => {
		row(itemHref(DESK, S)).click();
		expect(url()).toBe(itemHref(DESK, S));
		expect(focusedRoute()).toBe("b");
	});

	it("opens a plane row solo on a desk item, the desk untouched", () => {
		row("/p/t?x=1").click();
		expect(url()).toBe("/p/t?x=1");
		expect(currentRoute()).toEqual({ kind: "solo", plane: "t", params: { x: "1" } });
		expect(knownDesks()?.[DESK]).toEqual(WORK);
	});
});
