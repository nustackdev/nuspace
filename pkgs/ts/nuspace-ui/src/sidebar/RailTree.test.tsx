// The rail's icon and chevron slot, rendered in jsdom.
//
// jsdom applies no stylesheet, so the CSS swap itself (icon at rest, chevron on
// hover, one row at a time) is checked in a real browser. What is checked here
// is everything the swap stands on: every row carries both the icon and a real
// chevron button, the button only folds, and an open leaf says so.
//
// The tooltips are opened by focus, which opens a kit tooltip at once where a
// hover would wait out the delay. jsdom lays nothing out, so every box reads
// 0 wide and fits; a cut-off title is faked by stubbing its widths.

import { TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RailTree } from "./RailTree";
import { visibleRows } from "./tree";
import { childrenOf, coerceTree, ROOT_ID } from "./types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// a (with a1), b at the top.
const tree = coerceTree([
	{ id: ROOT_ID, kind: "space", title: "", parent: ROOT_ID, children: ["a", "b"] },
	{ id: "a", kind: "plane", title: "A", parent: ROOT_ID, children: ["a1"] },
	{ id: "a1", kind: "plane", title: "A1", parent: "a", children: [] },
	{ id: "b", kind: "plane", title: "B", parent: ROOT_ID, children: [] },
]);

// One plane with an emoji of its own.
const emojiTree = coerceTree([
	{ id: ROOT_ID, kind: "space", title: "", parent: ROOT_ID, children: ["e"] },
	{ id: "e", kind: "plane", title: "E", parent: ROOT_ID, children: [], icon: "emoji:🚀" },
]);

let host: HTMLDivElement;
let root: Root;
const onToggle = vi.fn();
const pins = { ids: ["a"], pin: vi.fn(), unpin: vi.fn(), move: vi.fn() };

function render(expanded: string[], on = tree) {
	const rows = visibleRows(on, childrenOf(on, ROOT_ID), new Set(expanded));
	act(() => {
		root.render(
			<TooltipProvider>
				<RailTree
					tree={on}
					rows={rows}
					registered={[]}
					routes={[]}
					selKey=""
					onToggle={onToggle}
					reveal={() => {}}
					notify={() => {}}
					pins={pins}
				/>
			</TooltipProvider>,
		);
	});
}

const rowOf = (key: string) =>
	host.querySelector<HTMLElement>(`[role="treeitem"][data-rail-key="${key}"]`);
const chevronOf = (key: string) => rowOf(key)?.querySelector<HTMLButtonElement>("button");
const linkOf = (key: string) => rowOf(key)?.querySelector<HTMLAnchorElement>("a");
const moreOf = (key: string) =>
	rowOf(key)?.querySelector<HTMLButtonElement>('button[aria-label^="Actions for"]');
/** The open tooltip's text, or null. */
const tooltip = () => document.querySelector('[role="tooltip"]')?.textContent ?? null;

/** Make `key`'s title read as cut off by the ellipsis. */
function truncate(key: string) {
	const span = linkOf(key)?.querySelector("span");
	if (!span) throw new Error(`no title for ${key}`);
	Object.defineProperty(span, "scrollWidth", { configurable: true, value: 240 });
	Object.defineProperty(span, "clientWidth", { configurable: true, value: 120 });
}

/** A native drag event on `el`, with the one bit of dataTransfer a row uses. */
function drag(el: Element | null | undefined, type: "dragstart" | "dragend") {
	const e = new Event(type, { bubbles: true, cancelable: true });
	Object.defineProperty(e, "dataTransfer", {
		value: { effectAllowed: "", dropEffect: "", setData: () => {} },
	});
	act(() => {
		el?.dispatchEvent(e);
	});
}

// The tooltip's popper sizes itself with a ResizeObserver, which jsdom lacks.
globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;

beforeEach(() => {
	window.history.replaceState({}, "", "/");
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
	onToggle.mockClear();
	vi.clearAllMocks();
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

describe("rail icon and chevron slot", () => {
	it("gives every row, leaf or not, its icon and a chevron button", () => {
		render(["a"]);
		for (const key of ["a", "a1", "b"]) {
			const lane = rowOf(key)?.firstElementChild;
			expect(lane?.querySelector(":scope > svg")).not.toBeNull();
			expect(lane?.querySelector(":scope > button")).not.toBeNull();
		}
		expect(chevronOf("a")?.getAttribute("aria-label")).toBe("Collapse");
		expect(chevronOf("a")?.getAttribute("aria-expanded")).toBe("true");
		expect(chevronOf("b")?.getAttribute("aria-label")).toBe("Expand");
		expect(chevronOf("b")?.getAttribute("aria-expanded")).toBe("false");
		expect(rowOf("b")?.getAttribute("aria-expanded")).toBe("false");
	});

	it("stacks a click-through icon over a chevron hidden at rest", () => {
		render([]);
		const lane = rowOf("b")?.firstElementChild;
		// At opacity 0 the icon paints above the chevron, so it must never
		// take the pointer, or it eats the chevron's click.
		expect(lane?.querySelector("svg")?.getAttribute("class")).toContain("pointer-events-none");
		expect(chevronOf("b")?.className).toMatch(/(^| )opacity-0( |$)/);
		expect(chevronOf("b")?.className).toContain("group-hover/row:opacity-100");
	});

	it("draws a plane's own emoji in the icon's place, click-through too", () => {
		render([], emojiTree);
		const lane = rowOf("e")?.firstElementChild;
		const emoji = lane?.querySelector(":scope > span");
		expect(emoji?.textContent).toBe("🚀");
		expect(emoji?.getAttribute("class")).toContain("pointer-events-none");
		expect(emoji?.getAttribute("class")).toContain("size-4");
		expect(lane?.querySelector(":scope > svg")).toBeNull();
	});

	it("offers Change icon in the row's menu", () => {
		render([]);
		act(() => {
			moreOf("b")?.dispatchEvent(
				new PointerEvent("pointerdown", { bubbles: true, button: 0, pointerType: "mouse" }),
			);
		});
		const items = [...document.querySelectorAll('[role="menuitem"]')].map((i) => i.textContent);
		expect(items).toContain("Change icon");
	});

	it("offers Pin or Unpin in the row's menu, as the plane is", () => {
		const menu = (key: string) => {
			act(() => {
				moreOf(key)?.dispatchEvent(
					new PointerEvent("pointerdown", { bubbles: true, button: 0, pointerType: "mouse" }),
				);
			});
			return [...document.querySelectorAll<HTMLElement>('[role="menuitem"]')];
		};
		render([]);
		const unpin = menu("a").find((i) => i.textContent === "Unpin");
		act(() => unpin?.click());
		expect(pins.unpin).toHaveBeenCalledWith("a");
		const pin = menu("b").find((i) => i.textContent === "Pin");
		act(() => pin?.click());
		expect(pins.pin).toHaveBeenCalledWith("b");
	});

	it("opens a plane in a new browser tab from both menus", () => {
		const open = vi.spyOn(window, "open").mockReturnValue(null);
		render([]);
		act(() => {
			moreOf("b")?.dispatchEvent(
				new PointerEvent("pointerdown", { bubbles: true, button: 0, pointerType: "mouse" }),
			);
		});
		const items = [...document.querySelectorAll<HTMLElement>('[role="menuitem"]')];
		const labels = items.map((i) => i.textContent);
		expect(labels.indexOf("Open in new tab")).toBe(labels.indexOf("Open in split") + 1);
		act(() => items.find((i) => i.textContent === "Open in new tab")?.click());
		expect(open).toHaveBeenLastCalledWith("/b", "_blank", "noopener");

		act(() => {
			rowOf("a")?.dispatchEvent(
				new MouseEvent("contextmenu", { bubbles: true, cancelable: true, button: 2 }),
			);
		});
		const ctx = [...document.querySelectorAll<HTMLElement>('[role="menuitem"]')];
		act(() => ctx.find((i) => i.textContent === "Open in new tab")?.click());
		expect(open).toHaveBeenLastCalledWith("/a", "_blank", "noopener");
		open.mockRestore();
	});

	it("leaves a cmd/ctrl-click on a row to the browser", () => {
		render([]);
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
		act(() => linkOf("b")?.click());
		document.removeEventListener("click", after);
		expect(seen).toEqual([false, false, true]);
		expect(linkOf("b")?.getAttribute("href")).toBe("/b");
		expect(window.location.pathname).toBe("/b");
	});

	it("folds on a chevron click and never navigates", () => {
		render(["a"]);
		const outer = vi.fn();
		// Above the React root, so it sees what the row would.
		document.body.addEventListener("click", outer);
		act(() => chevronOf("a")?.click());
		document.body.removeEventListener("click", outer);
		expect(onToggle).toHaveBeenCalledWith("a");
		expect(outer).not.toHaveBeenCalled();
		expect(window.location.pathname).toBe("/");
	});

	it("keeps a press on the chevron from focusing it or starting a drag", () => {
		render([]);
		const down = new MouseEvent("mousedown", { bubbles: true, cancelable: true });
		chevronOf("b")?.dispatchEvent(down);
		expect(down.defaultPrevented).toBe(true);
	});

	it("presses the chevron with Enter without opening the plane", () => {
		render([]);
		const enter = new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true });
		act(() => {
			chevronOf("b")?.dispatchEvent(enter);
		});
		// The row's Enter would have prevented the press and opened the plane.
		expect(enter.defaultPrevented).toBe(false);
		expect(window.location.pathname).toBe("/");
	});

	it("unfolds a leaf into one muted line and nothing focusable", () => {
		render([]);
		expect(host.textContent).not.toContain("No planes inside");
		render(["b"]);
		expect(host.textContent).toContain("No planes inside");
		expect(host.querySelectorAll('[role="treeitem"]').length).toBe(2);
		render(["a"]);
		expect(host.textContent).not.toContain("No planes inside");
	});

	it("unfolds a folded leaf with ArrowRight and folds it with ArrowLeft", () => {
		render([]);
		const right = new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true });
		act(() => {
			rowOf("b")?.dispatchEvent(right);
		});
		expect(onToggle).toHaveBeenLastCalledWith("b");
		render(["b"]);
		const left = new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true });
		act(() => {
			rowOf("b")?.dispatchEvent(left);
		});
		expect(onToggle).toHaveBeenCalledTimes(2);
	});
});

describe("rail actions", () => {
	it("hangs split, add and more, in that order, in a fixed-width lane", () => {
		render([]);
		const lane = moreOf("b")?.parentElement;
		const labels = [...(lane?.querySelectorAll("button") ?? [])].map((b) =>
			b.getAttribute("aria-label"),
		);
		expect(labels).toEqual(["Open B in split", "Add plane in B", "Actions for B"]);
		// Sized for all three, so a title truncates at the same edge on every row.
		expect(lane?.className).toContain("w-rail-actions");
	});

	it("gives split and add a tooltip", () => {
		render([]);
		const lane = moreOf("b")?.parentElement;
		const [split, add] = lane?.querySelectorAll("button") ?? [];
		act(() => (split as HTMLElement).focus());
		expect(tooltip()).toBe("Open in split");
		act(() => (add as HTMLElement).focus());
		expect(tooltip()).toBe("Add plane inside");
	});
});

describe("rail tooltips", () => {
	it("drops the native title for a kit tooltip", () => {
		render([]);
		expect(host.querySelector("[title]")).toBeNull();
	});

	it("shows a title only when it is cut off", () => {
		render([]);
		act(() => linkOf("b")?.focus());
		expect(tooltip()).toBeNull();
		act(() => linkOf("b")?.blur());

		truncate("a");
		act(() => linkOf("a")?.focus());
		expect(tooltip()).toBe("A");
	});

	it("closes a title's tooltip on a drag and keeps it shut after", () => {
		render([]);
		truncate("a");
		act(() => linkOf("a")?.focus());
		expect(tooltip()).toBe("A");

		drag(rowOf("a"), "dragstart");
		expect(tooltip()).toBeNull();
		drag(rowOf("a"), "dragend");
		expect(tooltip()).toBeNull();
	});

	it("keeps More off the open menu and off the focus it hands back", async () => {
		render([]);
		act(() => moreOf("b")?.focus());
		expect(tooltip()).toBe("More");

		const enter = new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true });
		act(() => {
			moreOf("b")?.dispatchEvent(enter);
		});
		expect(document.querySelector('[role="menu"]')).not.toBeNull();
		expect(tooltip()).toBeNull();

		const esc = new KeyboardEvent("keydown", { key: "Escape", bubbles: true });
		act(() => {
			document.activeElement?.dispatchEvent(esc);
		});
		expect(document.querySelector('[role="menu"]')).toBeNull();
		// The menu hands focus back on the next tick.
		await act(() => new Promise((done) => setTimeout(done, 0)));
		expect(document.activeElement).toBe(moreOf("b"));
		expect(tooltip()).toBeNull();
	});
});
