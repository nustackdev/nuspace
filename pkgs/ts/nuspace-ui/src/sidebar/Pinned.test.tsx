// The pinned rows, rendered in jsdom.
//
// Drops are faked with a plain event carrying the bits of dataTransfer the
// rows read, and a row's box is stubbed so the pointer's half of it is known.

import { catchAnchors, TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { paneRule } from "../core/router";
import { HOME_PLANE } from "./nav";
import { Pinned, shownPins } from "./Pinned";
import { RailBody } from "./railHarness";
import { coerceTree, ROOT_ID } from "./types";
import { PLANE_MIME } from "./useRailDrag";
import { pinKey } from "./useRailFocus";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;

const tree = coerceTree([
	{
		id: ROOT_ID,
		kind: "space",
		title: "",
		parent: ROOT_ID,
		children: ["a", "b", "c", "d", HOME_PLANE],
	},
	{ id: "a", kind: "plane", title: "A", parent: ROOT_ID, children: [], icon: "emoji:🏠" },
	{ id: "b", kind: "plane", title: "B", parent: ROOT_ID, children: [] },
	{ id: "c", kind: "plane", title: "", parent: ROOT_ID, children: [] },
	{ id: "d", kind: "plane", title: "D", parent: ROOT_ID, children: [] },
	{ id: HOME_PLANE, kind: "plane", title: "Home", parent: ROOT_ID, children: [], system: true },
]);

let host: HTMLDivElement;
let root: Root;
// The shell's anchor catcher, which is where a row's link goes.
let release: () => void;
const pins = { ids: [] as string[], pin: vi.fn(), unpin: vi.fn(), move: vi.fn() };

function render(ids: string[], selKey = "", routes: string[] = []) {
	pins.ids = ids;
	act(() => {
		root.render(
			<TooltipProvider>
				<RailBody keys={shownPins(tree, ids).map(pinKey)}>
					<Pinned
						tree={tree}
						pins={{ ...pins }}
						routes={routes}
						selKey={selKey}
						reveal={() => {}}
						notify={vi.fn()}
					/>
				</RailBody>
			</TooltipProvider>,
		);
	});
}

const rowOf = (id: string) => host.querySelector<HTMLElement>(`[data-rail-key="${pinKey(id)}"]`);
const linkOf = (id: string) => rowOf(id)?.querySelector<HTMLAnchorElement>("a");
const order = () =>
	[...host.querySelectorAll<HTMLElement>('[data-rail-key^="pin:"]')].map((r) =>
		r.dataset.railKey?.slice(4),
	);

/** A native drag event at `clientY`, carrying `types` and `data`. */
function drag(
	el: Element | null | undefined,
	type: "dragstart" | "dragover" | "drop" | "dragend",
	{ clientY = 0, data = {} as Record<string, string> } = {},
): Event {
	const e = new Event(type, { bubbles: true, cancelable: true });
	Object.defineProperty(e, "clientY", { value: clientY });
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

/** Give `id`'s row a 30px box at the origin, so y < 15 is its top half. */
function box(id: string) {
	const el = rowOf(id);
	if (el) el.getBoundingClientRect = () => ({ top: 0, height: 30 }) as DOMRect;
}

beforeEach(() => {
	window.history.replaceState({}, "", "/");
	host = document.createElement("div");
	document.body.append(host);
	release = catchAnchors(host, paneRule);
	root = createRoot(host);
	vi.clearAllMocks();
});

afterEach(() => {
	act(() => root.unmount());
	release();
	host.remove();
});

describe("pinned rows", () => {
	it("are hidden, header too, when nothing pinned is in the tree", () => {
		render([]);
		expect(host.textContent).toBe("");
		render(["gone"]);
		expect(host.textContent).toBe("");
	});

	it("never draw a nav row's plane", () => {
		render([HOME_PLANE, "a"]);
		expect(order()).toEqual(["a"]);
	});

	it("draw the pins in order under a Pinned header, each with its icon and name", () => {
		render(["b", "gone", "a", "c"]);
		expect(host.textContent).toContain("Pinned");
		expect(order()).toEqual(["b", "a", "c"]);
		expect(rowOf("a")?.textContent).toContain("🏠");
		expect(rowOf("b")?.querySelector("svg")).not.toBeNull();
		expect(linkOf("c")?.textContent).toBe("Untitled");
	});

	it("wash the focused pane's plane like the selected row", () => {
		render(["a", "b", "c"], "a", ["a", "b"]);
		expect(linkOf("a")?.getAttribute("aria-current")).toBe("page");
		expect(rowOf("a")?.className).toContain("bg-rail-a2-fill");
		expect(rowOf("b")?.className).toContain("bg-rail-a1-fill");
		expect(linkOf("c")?.getAttribute("aria-current")).toBeNull();
	});

	it("open like a tree row: a click in place, cmd/ctrl-click left to the browser", () => {
		render(["a", "b"]);
		act(() => linkOf("a")?.click());
		expect(window.location.pathname).toBe("/a");
		// Above the React root: records what the row left, then keeps jsdom
		// from following the link.
		const seen: boolean[] = [];
		const after = (e: Event) => {
			seen.push(e.defaultPrevented);
			e.preventDefault();
		};
		document.addEventListener("click", after);
		for (const init of [{ metaKey: true }, { ctrlKey: true }]) {
			act(() => {
				linkOf("b")?.dispatchEvent(
					new MouseEvent("click", { bubbles: true, cancelable: true, ...init }),
				);
			});
		}
		document.removeEventListener("click", after);
		expect(seen).toEqual([false, false]);
		expect(linkOf("b")?.getAttribute("href")).toBe("/b");
		expect(window.location.pathname).toBe("/a");
	});

	it("carry a tree row's hover controls: open on desk, add inside, more", () => {
		render(["b"]);
		const labels = [...(rowOf("b")?.querySelectorAll("button") ?? [])].map((b) =>
			b.getAttribute("aria-label"),
		);
		expect(labels).toEqual(["Open B on desk", "Add plane in B", "Actions for B"]);
	});

	it("pin a tree row where it is dropped, and leave it to the tree", () => {
		render(["a", "b"]);
		box("b");
		const data = { [PLANE_MIME]: "d" };
		const over = drag(rowOf("b"), "dragover", { clientY: 2, data });
		expect(over.defaultPrevented).toBe(true);
		expect(host.querySelector('[aria-hidden="true"].bg-accent')).not.toBeNull();
		drag(rowOf("b"), "drop", { clientY: 2, data });
		expect(pins.pin).toHaveBeenCalledWith("d", 1);
		expect(pins.move).not.toHaveBeenCalled();
		expect(host.querySelector(".bg-accent")).toBeNull();
	});

	it("never pin a nav row's plane dropped on them", () => {
		render(["a"]);
		box("a");
		drag(rowOf("a"), "drop", { clientY: 2, data: { [PLANE_MIME]: HOME_PLANE } });
		expect(pins.pin).not.toHaveBeenCalled();
	});

	it("reorder a pin dragged among them", () => {
		render(["a", "b", "c"]);
		box("a");
		drag(rowOf("c"), "dragstart");
		drag(rowOf("a"), "dragover", { clientY: 2 });
		drag(rowOf("a"), "drop", { clientY: 2 });
		expect(pins.move).toHaveBeenCalledWith("c", 0);
		expect(pins.pin).not.toHaveBeenCalled();
	});

	it("do nothing for a pin dropped where it is, or a drag they do not know", () => {
		render(["a", "b"]);
		box("a");
		drag(rowOf("a"), "dragstart");
		drag(rowOf("a"), "drop", { clientY: 20 });
		drag(rowOf("a"), "dragend");
		const foreign = drag(rowOf("b"), "dragover", { data: { "text/plain": "x" } });
		expect(foreign.defaultPrevented).toBe(false);
		drag(rowOf("b"), "drop", { data: { "text/plain": "x" } });
		expect(pins.move).not.toHaveBeenCalled();
		expect(pins.pin).not.toHaveBeenCalled();
	});
});
