// The pinned row, rendered in jsdom.
//
// jsdom lays nothing out, so the fades and the wheel's sideways scroll are
// checked in a real browser. Drops are faked with a plain event carrying the
// bits of dataTransfer the row reads, and an icon's box is stubbed so the
// pointer's half of it is known.

import { TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PinnedRow } from "./PinnedRow";
import { coerceTree, ROOT_ID } from "./types";
import { PLANE_MIME } from "./useRailDrag";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;

const tree = coerceTree([
	{ id: ROOT_ID, kind: "space", title: "", parent: ROOT_ID, children: ["a", "b", "c", "d"] },
	{ id: "a", kind: "plane", title: "A", parent: ROOT_ID, children: [], icon: "emoji:🏠" },
	{ id: "b", kind: "plane", title: "B", parent: ROOT_ID, children: [] },
	{ id: "c", kind: "plane", title: "", parent: ROOT_ID, children: [] },
	{ id: "d", kind: "plane", title: "D", parent: ROOT_ID, children: [] },
]);

let host: HTMLDivElement;
let root: Root;
const pins = { ids: [] as string[], pin: vi.fn(), unpin: vi.fn(), move: vi.fn() };

function render(ids: string[], selKey = "", routes: string[] = []) {
	pins.ids = ids;
	act(() => {
		root.render(
			<TooltipProvider>
				<PinnedRow
					tree={tree}
					pins={{ ...pins }}
					registered={[]}
					routes={routes}
					selKey={selKey}
					reveal={() => {}}
				/>
			</TooltipProvider>,
		);
	});
}

const pinOf = (id: string) => host.querySelector<HTMLAnchorElement>(`[data-pin="${id}"]`);
const order = () => [...host.querySelectorAll("[data-pin]")].map((a) => a.getAttribute("data-pin"));

/** A native drag event at `clientX`, carrying `types` and `data`. */
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

/** Give `id`'s icon a 28px box at the origin, so x < 14 is its left half. */
function box(id: string) {
	const el = pinOf(id);
	if (el) el.getBoundingClientRect = () => ({ left: 0, width: 28 }) as DOMRect;
}

beforeEach(() => {
	window.history.replaceState({}, "", "/");
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
	vi.clearAllMocks();
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

describe("pinned row", () => {
	it("is hidden when nothing is pinned, or nothing pinned is in the tree", () => {
		render([]);
		expect(host.querySelector("nav")).toBeNull();
		render(["gone"]);
		expect(host.querySelector("nav")).toBeNull();
	});

	it("draws the pins in order, icon only, named for a screen reader", () => {
		render(["b", "gone", "a", "c"]);
		expect(order()).toEqual(["b", "a", "c"]);
		expect(pinOf("a")?.textContent).toBe("🏠");
		expect(pinOf("b")?.querySelector("svg")).not.toBeNull();
		expect(pinOf("c")?.getAttribute("aria-label")).toBe("Untitled");
	});

	it("shows the name in a tooltip", () => {
		render(["a", "b"]);
		act(() => pinOf("b")?.focus());
		expect(document.querySelector('[role="tooltip"]')?.textContent).toBe("B");
	});

	it("washes the focused pane's plane like the selected row", () => {
		render(["a", "b", "c"], "a", ["a", "b"]);
		expect(pinOf("a")?.getAttribute("aria-current")).toBe("page");
		expect(pinOf("a")?.className).toContain("bg-rail-selected");
		expect(pinOf("b")?.className).toContain("bg-rail-open");
		expect(pinOf("c")?.getAttribute("aria-current")).toBeNull();
	});

	it("opens like a tree row: a click in place, cmd/ctrl-click as a split", () => {
		render(["a", "b"]);
		act(() => pinOf("a")?.click());
		expect(window.location.pathname).toBe("/a");
		act(() => {
			pinOf("b")?.dispatchEvent(
				new MouseEvent("click", { bubbles: true, cancelable: true, metaKey: true }),
			);
		});
		expect(window.location.pathname).toBe("/a+b");
	});

	it("pins a tree row where it is dropped, and leaves it to the tree", () => {
		render(["a", "b"]);
		box("b");
		const data = { [PLANE_MIME]: "d" };
		const over = drag(pinOf("b"), "dragover", { clientX: 2, data });
		expect(over.defaultPrevented).toBe(true);
		expect(pinOf("b")?.querySelector('[aria-hidden="true"].bg-accent')).not.toBeNull();
		drag(pinOf("b"), "drop", { clientX: 2, data });
		expect(pins.pin).toHaveBeenCalledWith("d", 1);
		expect(pins.move).not.toHaveBeenCalled();
		expect(host.querySelector(".bg-accent")).toBeNull();
	});

	it("reorders a pin dragged within the row", () => {
		render(["a", "b", "c"]);
		box("a");
		drag(pinOf("c"), "dragstart");
		drag(pinOf("a"), "dragover", { clientX: 2 });
		drag(pinOf("a"), "drop", { clientX: 2 });
		expect(pins.move).toHaveBeenCalledWith("c", 0);
		expect(pins.pin).not.toHaveBeenCalled();
	});

	it("does nothing for a pin dropped where it is, or a drag it does not know", () => {
		render(["a", "b"]);
		box("a");
		drag(pinOf("a"), "dragstart");
		drag(pinOf("a"), "drop", { clientX: 20 });
		drag(pinOf("a"), "dragend");
		const foreign = drag(pinOf("b"), "dragover", { data: { "text/plain": "x" } });
		expect(foreign.defaultPrevented).toBe(false);
		drag(pinOf("b"), "drop", { data: { "text/plain": "x" } });
		expect(pins.move).not.toHaveBeenCalled();
		expect(pins.pin).not.toHaveBeenCalled();
	});
});
