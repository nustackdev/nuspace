// The one header: each screen (the sidebar, a plane, a desk) wears exactly
// one, a desk's pages none of their own, and the desk's pager buttons turn
// its pages, held at the ends, the counter following.

import { TooltipProvider, TouchProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import * as router from "../core/router";
import type { Desk } from "../desk/model";
import { MobileDesk } from "./desk/MobileDesk";
import { MobilePlane } from "./plane/MobilePlane";
import { MobileSidebar } from "./sidebar/MobileSidebar";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const DESK = "desk0001";
const STRIP = "item01";
const WIDTH = 375;

const OPS: Desk = {
	name: "Ops",
	items: [
		{
			id: STRIP,
			kind: "strip",
			columns: ["a", "b", "c"].map((plane) => ({
				panes: [{ share: 1, original: { plane, params: {} } }],
			})),
		},
	],
};

let host: HTMLDivElement;
let root: Root;
const restore: (() => void)[] = [];

/** jsdom lays nothing out: a page is WIDTH wide, and a scroll lands at once. */
function layout() {
	const width = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth");
	Object.defineProperty(HTMLElement.prototype, "clientWidth", {
		configurable: true,
		get: () => WIDTH,
	});
	const scrollTo = Element.prototype.scrollTo;
	Element.prototype.scrollTo = function (this: Element, opts?: ScrollToOptions | number) {
		const left = typeof opts === "object" ? (opts.left ?? 0) : 0;
		this.scrollLeft = left;
		this.dispatchEvent(new Event("scroll"));
	} as typeof Element.prototype.scrollTo;
	const RO = globalThis.ResizeObserver;
	globalThis.ResizeObserver = class {
		observe() {}
		unobserve() {}
		disconnect() {}
	} as unknown as typeof ResizeObserver;
	restore.push(() => {
		if (width) Object.defineProperty(HTMLElement.prototype, "clientWidth", width);
		Element.prototype.scrollTo = scrollTo;
		globalThis.ResizeObserver = RO;
	});
}

beforeEach(() => {
	router.resetRouter();
	layout();
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
	for (const undo of restore.splice(0)) undo();
});

function draw(node: React.ReactNode) {
	act(() => {
		root.render(
			<TouchProvider value>
				<TooltipProvider>{node}</TooltipProvider>
			</TouchProvider>,
		);
	});
}

const headers = () => host.querySelectorAll("[data-mobile-header]");
const count = () => host.querySelector("[data-desk-count]")?.textContent;
const step = (which: "prev" | "next") =>
	host.querySelector<HTMLButtonElement>(`[data-desk-step="${which}"]`);

function deskRoute(focus: string): Extract<router.Route, { kind: "item" }> {
	return { kind: "item", desk: DESK, name: OPS.name, item: OPS.items[0], focus };
}

function desk(focus = "a") {
	act(() => router.setDesks({ [DESK]: OPS }));
	draw(<MobileDesk viewerPath={["viewer"]} route={deskRoute(focus)} cellSpecs={[]} />);
}

describe("one header a screen", () => {
	it("the sidebar wears one, the wordmark alone: a new plane is the dock's +", () => {
		draw(<MobileSidebar />);
		expect(headers()).toHaveLength(1);
		expect(headers()[0].textContent).toContain("space");
		expect(headers()[0].querySelector("button")).toBeNull();
	});

	it("a plane wears one, its title in it", () => {
		draw(<MobilePlane viewerPath={["viewer"]} planeId="p1" cellSpecs={[]} />);
		expect(headers()).toHaveLength(1);
		expect(host.querySelector("[data-header-title]")).not.toBeNull();
	});

	it("a desk wears one, and its pages none of their own", () => {
		desk();
		expect(headers()).toHaveLength(1);
		expect(host.querySelectorAll("[data-desk-page]")).toHaveLength(3);
		expect(headers()[0].textContent).toContain("Ops");
	});
});

describe("the desk's pager", () => {
	it("turns the pages with its buttons, held at the ends", () => {
		desk();
		expect(count()).toBe("1/3");
		expect(step("prev")?.disabled).toBe(true);
		act(() => step("next")?.click());
		expect(count()).toBe("2/3");
		expect(step("prev")?.disabled).toBe(false);
		act(() => step("next")?.click());
		expect(count()).toBe("3/3");
		expect(step("next")?.disabled).toBe(true);
		act(() => step("prev")?.click());
		expect(count()).toBe("2/3");
	});

	it("follows a swipe", () => {
		desk();
		const pager = host.querySelector<HTMLElement>("[data-desk-pager]");
		act(() => {
			if (!pager) return;
			pager.scrollLeft = 2 * WIDTH;
			pager.dispatchEvent(new Event("scroll"));
		});
		expect(count()).toBe("3/3");
	});

	it("has no dots, and no pager on a single page", () => {
		desk();
		// The header, then the pager: no strip of dots between them.
		const screen = host.querySelector("[data-desk-screen]");
		expect([...(screen?.children ?? [])].map((e) => e.tagName)).toEqual(["HEADER", "DIV"]);
		act(() =>
			router.setDesks({
				[DESK]: {
					name: "Solo",
					items: [{ id: STRIP, kind: "plane", original: { plane: "a", params: {} } }],
				},
			}),
		);
		draw(
			<MobileDesk
				viewerPath={["viewer"]}
				route={{
					kind: "item",
					desk: DESK,
					name: "Solo",
					item: { id: STRIP, kind: "plane", original: { plane: "a", params: {} } },
					focus: "a",
				}}
				cellSpecs={[]}
			/>,
		);
		expect(step("next")).toBeNull();
		expect(count()).toBeUndefined();
	});
});
