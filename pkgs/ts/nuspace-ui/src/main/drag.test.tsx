// Moving panes around, rendered in jsdom: a plane dropped from the rail onto
// the panes, a tab dragged along the bar, and the widths that go with a pane.
//
// jsdom lays nothing out, so a pane's or a tab's box is stubbed where the
// pointer's half of it matters, and drops are faked with a plain event
// carrying the bits of dataTransfer the handlers read.

import { TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { currentRoutes } from "../core/router";
import { PaneMenu } from "../pane/PaneMenu";
import { coerceMeta } from "../plane/types";
import { PIN_MIME } from "../sidebar/PinnedRow";
import { PLANE_MIME } from "../sidebar/useRailDrag";
import { TAB_MIME, TabBar, tabDropIndex } from "./TabBar";
import { paneSlot, useCanvasDrop } from "./useCanvasDrop";
import { widthsOf } from "./usePaneWidths";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;

// The tab bar scrolls the focused tab into view, which jsdom has no part of.
globalThis.CSS ??= { escape: (s: string) => s } as unknown as typeof CSS;
Element.prototype.scrollIntoView ??= () => {};
window.matchMedia ??= (() => ({ matches: false })) as unknown as typeof window.matchMedia;

let host: HTMLDivElement;
let root: Root;

/** A native drag event at `clientX`, carrying `data`. */
function drag(
	el: Element | null,
	type: "dragstart" | "dragover" | "drop" | "dragend",
	{ clientX = 0, data = {} as Record<string, string> } = {},
): Event {
	const e = new Event(type, { bubbles: true, cancelable: true });
	Object.defineProperty(e, "clientX", { value: clientX });
	Object.defineProperty(e, "dataTransfer", {
		value: {
			effectAllowed: "",
			dropEffect: "",
			types: Object.keys(data),
			setData: () => {},
			getData: (k: string) => data[k] ?? "",
		},
	});
	act(() => {
		el?.dispatchEvent(e);
	});
	return e;
}

/** Give `el` a 100px box at the origin, so x < 50 is its left half. */
function box(el: Element | null) {
	if (el) el.getBoundingClientRect = () => ({ left: 0, width: 100 }) as DOMRect;
}

function at(path: string) {
	window.history.replaceState({}, "", path);
}

beforeEach(() => {
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

describe("pane widths", () => {
	it("travel with their panes, and reset when the set changes", () => {
		const state = { key: "a+b+c", px: { a: 100, b: 200, c: 300 } };
		expect(widthsOf(state, ["a", "b", "c"])).toEqual([100, 200, 300]);
		expect(widthsOf(state, ["c", "a", "b"])).toEqual([300, 100, 200]);
		expect(widthsOf(state, ["a", "b"])).toBeNull();
		expect(widthsOf(state, ["a", "b", "d"])).toBeNull();
		expect(widthsOf(null, ["a"])).toBeNull();
	});
});

describe("drop on the panes", () => {
	function Strip({ routes }: { routes: string[] }) {
		const { target, dropProps } = useCanvasDrop(routes);
		return (
			<div data-strip {...dropProps}>
				{routes.map((id) => (
					<section key={id} data-pane={id} data-drop={target?.id === id ? target.edge : ""} />
				))}
			</div>
		);
	}
	const paneOf = (id: string) => host.querySelector(`[data-pane="${id}"]`);

	it("counts the slot off the pane and its half", () => {
		expect(paneSlot(["a", "b"], { id: "a", edge: "before" })).toBe(0);
		expect(paneSlot(["a", "b"], { id: "a", edge: "after" })).toBe(1);
		expect(paneSlot(["a", "b"], { id: "b", edge: "after" })).toBe(2);
		expect(paneSlot(["a", "b"], { id: "x", edge: "before" })).toBe(2);
	});

	it("opens a tree row before the pane on its left half, after on its right", () => {
		at("/a+b");
		act(() => root.render(<Strip routes={["a", "b"]} />));
		box(paneOf("b"));
		const data = { [PLANE_MIME]: "c" };
		const over = drag(paneOf("b"), "dragover", { clientX: 10, data });
		expect(over.defaultPrevented).toBe(true);
		expect(paneOf("b")?.getAttribute("data-drop")).toBe("before");
		drag(paneOf("b"), "dragover", { clientX: 90, data });
		expect(paneOf("b")?.getAttribute("data-drop")).toBe("after");
		drag(paneOf("b"), "drop", { clientX: 10, data });
		expect(currentRoutes()).toEqual(["a", "c", "b"]);
		expect(paneOf("b")?.getAttribute("data-drop")).toBe("");
	});

	it("opens a pin too, after a lone pane", () => {
		at("/a");
		act(() => root.render(<Strip routes={["a"]} />));
		box(paneOf("a"));
		drag(paneOf("a"), "drop", { clientX: 90, data: { [PIN_MIME]: "p" } });
		expect(currentRoutes()).toEqual(["a", "p"]);
	});

	it("only focuses a plane already open, as Open in split does", () => {
		at("/a+b");
		act(() => root.render(<Strip routes={["a", "b"]} />));
		box(paneOf("b"));
		drag(paneOf("b"), "drop", { clientX: 90, data: { [PLANE_MIME]: "a" } });
		expect(currentRoutes()).toEqual(["a", "b"]);
	});

	it("ignores a tab's drag and anything else", () => {
		at("/a+b");
		act(() => root.render(<Strip routes={["a", "b"]} />));
		box(paneOf("a"));
		for (const data of [{ [TAB_MIME]: "b" }, { "text/plain": "x" }] as Record<string, string>[]) {
			expect(drag(paneOf("a"), "dragover", { data }).defaultPrevented).toBe(false);
			drag(paneOf("a"), "drop", { data });
		}
		expect(currentRoutes()).toEqual(["a", "b"]);
		expect(paneOf("a")?.getAttribute("data-drop")).toBe("");
	});
});

describe("tab drag", () => {
	const routes = ["a", "b", "c"];
	const tabOf = (id: string) => host.querySelector(`[data-tab="${id}"]`);

	function render() {
		const stripRef = { current: null };
		act(() => {
			root.render(
				<TooltipProvider>
					<TabBar
						routes={routes}
						planes={{}}
						focused="a"
						stripRef={stripRef}
						onMeta={() => {}}
						onRename={() => {}}
						deleteOf={() => undefined}
					/>
				</TooltipProvider>,
			);
		});
	}

	it("counts the drop index without the dragged tab", () => {
		expect(tabDropIndex(routes, "a", { index: 2, edge: "after" })).toBe(2);
		expect(tabDropIndex(routes, "a", { index: 1, edge: "before" })).toBeNull();
		expect(tabDropIndex(routes, "a", { index: 0, edge: "after" })).toBeNull();
		expect(tabDropIndex(routes, "c", { index: 0, edge: "before" })).toBe(0);
		expect(tabDropIndex(routes, "c", { index: 1, edge: "after" })).toBeNull();
	});

	it("moves a pane to where its tab is dropped, with an accent line on the way", () => {
		at("/a+b+c");
		render();
		box(tabOf("c"));
		drag(tabOf("a"), "dragstart");
		drag(tabOf("c"), "dragover", { clientX: 90 });
		expect(tabOf("c")?.querySelector('[aria-hidden="true"].bg-accent')).not.toBeNull();
		drag(tabOf("c"), "drop", { clientX: 90 });
		expect(currentRoutes()).toEqual(["b", "c", "a"]);
		expect(host.querySelector(".bg-accent")).toBeNull();
	});

	it("takes no drag but its own tabs'", () => {
		at("/a+b+c");
		render();
		box(tabOf("a"));
		const over = drag(tabOf("a"), "dragover", { data: { [PLANE_MIME]: "x" } });
		expect(over.defaultPrevented).toBe(false);
		drag(tabOf("a"), "drop", { data: { [PLANE_MIME]: "x" } });
		expect(currentRoutes()).toEqual(["a", "b", "c"]);
	});
});

describe("pane menu", () => {
	it("opens the plane in a new browser tab", () => {
		const open = vi.spyOn(window, "open").mockReturnValue(null);
		act(() => {
			root.render(<PaneMenu planeId="a" meta={coerceMeta({})} onChange={() => {}} open />);
		});
		const item = [...document.querySelectorAll<HTMLElement>('[role="menuitem"]')].find(
			(b) => b.textContent === "Open in new tab",
		);
		act(() => item?.click());
		expect(open).toHaveBeenCalledWith("/a", "_blank", "noopener");
		open.mockRestore();
	});
});
