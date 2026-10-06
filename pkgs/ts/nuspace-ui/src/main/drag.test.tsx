// Moving panes around the desk, rendered in jsdom: a plane dropped from the
// rail onto the panes, a pane dragged by its bar, the widths that go with a
// pane, and the dock's map of it all.
//
// jsdom lays nothing out, so a pane's box is stubbed where the pointer's half
// of it matters, and drops are faked with a plain event carrying the bits of
// dataTransfer the handlers read.

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { currentRoutes } from "../core/router";
import { PaneMenu } from "../pane/PaneMenu";
import { coerceMeta } from "../plane/types";
import { PIN_MIME } from "../sidebar/PinnedRow";
import { PLANE_MIME } from "../sidebar/useRailDrag";
import { dockLayout } from "./Dock";
import { PANE_MIME, paneSlot, useCanvasDrop } from "./useCanvasDrop";
import { widthsOf } from "./usePaneWidths";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;

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

	it("only focuses a plane already open, as Open on desk does", () => {
		at("/a+b");
		act(() => root.render(<Strip routes={["a", "b"]} />));
		box(paneOf("b"));
		drag(paneOf("b"), "drop", { clientX: 90, data: { [PLANE_MIME]: "a" } });
		expect(currentRoutes()).toEqual(["a", "b"]);
	});

	it("moves a pane dragged by its bar to the half it is dropped on", () => {
		at("/a+b+c");
		act(() => root.render(<Strip routes={["a", "b", "c"]} />));
		box(paneOf("c"));
		const data = { [PANE_MIME]: "a" };
		expect(drag(paneOf("c"), "dragover", { clientX: 90, data }).defaultPrevented).toBe(true);
		drag(paneOf("c"), "drop", { clientX: 90, data });
		expect(currentRoutes()).toEqual(["b", "c", "a"]);
	});

	it("leaves a pane dropped beside itself where it is", () => {
		at("/a+b");
		act(() => root.render(<Strip routes={["a", "b"]} />));
		box(paneOf("b"));
		drag(paneOf("b"), "drop", { clientX: 10, data: { [PANE_MIME]: "a" } });
		expect(currentRoutes()).toEqual(["a", "b"]);
	});

	it("ignores anything else", () => {
		at("/a+b");
		act(() => root.render(<Strip routes={["a", "b"]} />));
		box(paneOf("a"));
		for (const data of [{ "text/plain": "x" }] as Record<string, string>[]) {
			expect(drag(paneOf("a"), "dragover", { data }).defaultPrevented).toBe(false);
			drag(paneOf("a"), "drop", { data });
		}
		expect(currentRoutes()).toEqual(["a", "b"]);
		expect(paneOf("a")?.getAttribute("data-drop")).toBe("");
	});
});

describe("dock", () => {
	const panes = [
		{ id: "a", x: 0, w: 600 },
		{ id: "b", x: 600, w: 600 },
		{ id: "c", x: 1200, w: 800 },
	];

	it("draws only when some scroll leaves a pane fully out of view", () => {
		// c starts at 1200: past a 1000 window with the desk at its start.
		expect(dockLayout({ left: 0, view: 1000, total: 2000, panes })).not.toBeNull();
		// Wide enough that c starts inside it, and a still shows with the desk
		// at its end: a piece of every pane at every scroll.
		expect(dockLayout({ left: 0, view: 1500, total: 2000, panes })).toBeNull();
		const two = [
			{ id: "a", x: 0, w: 900 },
			{ id: "b", x: 900, w: 900 },
		];
		expect(dockLayout({ left: 0, view: 1200, total: 1800, panes: two })).toBeNull();
		// The first pane ends before the desk's last window starts.
		const wide = [
			{ id: "a", x: 0, w: 400 },
			{ id: "b", x: 400, w: 1400 },
		];
		expect(dockLayout({ left: 0, view: 1300, total: 1800, panes: wide })).not.toBeNull();
	});

	it("sizes each chip as its share of the desk, and the window as the view's", () => {
		const layout = dockLayout({ left: 500, view: 500, total: 2000, panes });
		expect(layout?.chips.map((c) => [c.id, c.left, c.width])).toEqual([
			["a", 0, 30],
			["b", 30, 30],
			["c", 60, 40],
		]);
		expect(layout?.window).toEqual({ left: 25, width: 25 });
	});

	it("marks the chips whose panes are on screen", () => {
		const on = (left: number) =>
			dockLayout({ left, view: 500, total: 2000, panes })
				?.chips.filter((c) => c.onScreen)
				.map((c) => c.id);
		expect(on(0)).toEqual(["a"]);
		expect(on(500)).toEqual(["a", "b"]);
		expect(on(1000)).toEqual(["b", "c"]);
		// A sliver of a pane at the edge does not count.
		expect(on(580)).toEqual(["b"]);
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

	function item(label: string) {
		return [...document.querySelectorAll<HTMLElement>('[role="menuitem"]')].find(
			(b) => b.textContent === label,
		);
	}

	it("closes the panes to the right, and the others", () => {
		at("/a+b+c");
		act(() => {
			root.render(<PaneMenu planeId="b" meta={coerceMeta({})} onChange={() => {}} open />);
		});
		act(() => item("Close to the right")?.click());
		expect(currentRoutes()).toEqual(["a", "b"]);
		at("/a+b+c");
		act(() => root.render(<PaneMenu planeId="b" meta={null} onChange={() => {}} open />));
		expect(item("Open in new tab")).toBeUndefined();
		act(() => item("Close others")?.click());
		expect(currentRoutes()).toEqual(["b"]);
	});

	it("keeps the desk items it cannot use, disabled", () => {
		at("/a+b");
		act(() => {
			root.render(<PaneMenu planeId="b" meta={null} onChange={() => {}} open />);
		});
		expect(item("Close to the right")?.hasAttribute("data-disabled")).toBe(true);
		expect(item("Close others")?.hasAttribute("data-disabled")).toBe(false);
	});

	it("has no desk items on a lone pane", () => {
		at("/a");
		act(() => {
			root.render(<PaneMenu planeId="a" meta={coerceMeta({})} onChange={() => {}} open />);
		});
		expect(item("Close")).toBeUndefined();
		expect(item("Close others")).toBeUndefined();
		expect(item("Open in new tab")).toBeDefined();
	});
});
