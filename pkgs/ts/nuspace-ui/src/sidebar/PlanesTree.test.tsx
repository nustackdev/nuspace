// The Planes tree, rendered in jsdom: the icon and chevron slot, the row's
// one trailing action, its menus, rename, drop and the links.
//
// jsdom applies no stylesheet, so the CSS swap itself (icon at rest, chevron on
// hover, one row at a time) is checked in a real browser. What is checked here
// is everything the swap stands on: every row carries both the icon and a real
// chevron button, the button only folds, and an open leaf says so.
//
// The tooltips are opened by focus, which opens a kit tooltip at once where a
// hover would wait out the delay. jsdom lays nothing out, so every box reads
// 0 wide and fits; a cut-off title is faked by stubbing its widths.

import { catchAnchors, TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { currentRoutes, focusPane, knownDesks, setDesks, setRoles } from "../core/router";
import type { Desk } from "../desk/model";
import { PLANE_MIME } from "./drag";
import { SidebarBody } from "./harness";
import { sidebarRule } from "./links";
import { PlanesTree } from "./PlanesTree";
import { visibleRows } from "./tree";
import { childrenOf, coerceTree, ROOT_ID } from "./types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

/** Land on a strip of `planes`, one column each, the last one focused. */
function onDesk(...planes: string[]): Desk {
	const columns = planes.map((plane) => ({
		panes: [{ share: 1, original: { plane, params: {} } }],
	}));
	const desk: Desk = { name: "", items: [{ id: "strip1", kind: "strip", columns }] };
	setRoles({ home: "h", settings: "", search: "" });
	setDesks({ desk0001: desk });
	window.history.replaceState(null, "", "/desk0001/strip1");
	focusPane("desk0001", "strip1", planes.at(-1) ?? "");
	return desk;
}

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
// The sidebar's anchor catcher, which is where a row's link goes.
let release: () => void;
const onToggle = vi.fn();
const notify = vi.fn();

function render(expanded: string[], on = tree, selKey = "") {
	const rows = visibleRows(on, childrenOf(on, ROOT_ID), new Set(expanded));
	act(() => {
		root.render(
			<TooltipProvider>
				<SidebarBody keys={rows.map((r) => r.key)}>
					<PlanesTree
						tree={on}
						rows={rows}
						selKey={selKey}
						onToggle={onToggle}
						reveal={() => {}}
						notify={notify}
					/>
				</SidebarBody>
			</TooltipProvider>,
		);
	});
}

const rowOf = (key: string) =>
	host.querySelector<HTMLElement>(`[role="treeitem"][data-key="${key}"]`);
const chevronOf = (key: string) => rowOf(key)?.querySelector<HTMLButtonElement>("button");
const linkOf = (key: string) => rowOf(key)?.querySelector<HTMLAnchorElement>("a");
const moreOf = (key: string) =>
	rowOf(key)?.querySelector<HTMLButtonElement>('button[aria-label^="Actions for"]');
/** The open tooltip's text, or null. */
const tooltip = () => document.querySelector('[role="tooltip"]')?.textContent ?? null;

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
	release = catchAnchors(host, sidebarRule);
	root = createRoot(host);
	onToggle.mockClear();
	vi.clearAllMocks();
});

afterEach(() => {
	act(() => root.unmount());
	release();
	host.remove();
});

describe("tree row icon and chevron slot", () => {
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

	it("offers no Close: a tree row is the plane, not a desk item", () => {
		const labels = (key: string) => {
			act(() => {
				moreOf(key)?.dispatchEvent(
					new PointerEvent("pointerdown", { bubbles: true, button: 0, pointerType: "mouse" }),
				);
			});
			return [...document.querySelectorAll<HTMLElement>('[role="menuitem"]')].map(itemLabel);
		};
		// Even while the plane is a pane of the strip the tab shows: its desk row closes it.
		onDesk("a", "b");
		render([]);
		expect(labels("a")).not.toContain("Close");
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
		const labels = items.map(itemLabel);
		expect(labels.indexOf("Open in new tab")).toBe(labels.indexOf("Open") + 1);
		expect(labels).not.toContain("Open on desk");
		act(() => items.find((i) => itemLabel(i) === "Open in new tab")?.click());
		expect(open).toHaveBeenLastCalledWith("/b", "_blank", "noopener");

		act(() => {
			rowOf("a")?.dispatchEvent(
				new MouseEvent("contextmenu", { bubbles: true, cancelable: true, button: 2 }),
			);
		});
		const ctx = [...document.querySelectorAll<HTMLElement>('[role="menuitem"]')];
		act(() => ctx.find((i) => itemLabel(i) === "Open in new tab")?.click());
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

	it("reads an Option-click on a row as a plain one: the plane solo", () => {
		window.history.replaceState(null, "", "/a");
		render([]);
		act(() => {
			linkOf("b")?.dispatchEvent(
				new MouseEvent("click", { bubbles: true, cancelable: true, altKey: true }),
			);
		});
		expect(window.location.pathname).toBe("/b");
	});

	it("opens a plain click on a desk item as the plane solo, the desk untouched", () => {
		const desk = onDesk("x", "y");
		render([]);
		act(() => linkOf("b")?.click());
		expect(window.location.pathname).toBe("/b");
		expect(currentRoutes()).toEqual(["b"]);
		expect(knownDesks()?.desk0001).toEqual(desk);
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

describe("tree row trailing action", () => {
	it("carries the `+` and the `...` on hover, sized only when shown", () => {
		render([]);
		const lane = moreOf("b")?.parentElement;
		const labels = [...(lane?.querySelectorAll("button") ?? [])].map((b) =>
			b.getAttribute("aria-label"),
		);
		expect(labels).toEqual(["Add plane in B", "Actions for B"]);
		// Zero wide at rest, so a title runs to the row's edge. Still in the
		// DOM, for the keyboard.
		const cls = lane?.className.split(" ") ?? [];
		expect(cls).toContain("w-0");
		expect(cls).toContain("group-hover/row:w-auto");
		expect(cls).toContain("has-focus-visible:w-auto");
	});

	it("keeps Add plane inside in the menu, and no open on desk", () => {
		render([]);
		act(() => {
			moreOf("b")?.dispatchEvent(
				new PointerEvent("pointerdown", { bubbles: true, button: 0, pointerType: "mouse" }),
			);
		});
		const items = [...document.querySelectorAll<HTMLElement>('[role="menuitem"]')].map(itemLabel);
		expect(items).not.toContain("Open on desk");
		expect(items).toContain("Add plane inside");
	});
});

describe("tree row selection", () => {
	it("selects the focused pane's plane with the quiet fill, and only it", () => {
		render([], tree, "b");
		expect(rowOf("b")?.getAttribute("aria-selected")).toBe("true");
		expect(rowOf("b")?.className).toContain(" bg-bg-press");
		expect(rowOf("a")?.getAttribute("aria-selected")).toBe("false");
		expect(rowOf("a")?.className).not.toContain(" bg-bg-press");
		expect(rowOf("a")?.className).toContain("hover:bg-bg-hover");
	});

	it("opens the row's plane with Enter", () => {
		window.history.replaceState(null, "", "/a");
		render([]);
		act(() => {
			rowOf("b")?.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
		});
		expect(window.location.pathname).toBe("/b");
	});
});

describe("tree row rename, delete and drop", () => {
	it("renames in place on a double click, and sends it on Enter", () => {
		render([]);
		act(() => {
			linkOf("b")?.dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
		});
		const input = rowOf("b")?.querySelector<HTMLInputElement>("input");
		expect(input?.getAttribute("aria-label")).toBe("Rename B");
		act(() => {
			if (input) input.value = "Bee";
			input?.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
		});
		expect(notify).toHaveBeenCalledWith("plane.rename", { plane_id: "b", title: "Bee" });
		expect(rowOf("b")?.querySelector("input")).toBeNull();
	});

	it("offers Delete in the menu", () => {
		render([]);
		act(() => {
			moreOf("b")?.dispatchEvent(
				new PointerEvent("pointerdown", { bubbles: true, button: 0, pointerType: "mouse" }),
			);
		});
		const items = [...document.querySelectorAll<HTMLElement>('[role="menuitem"]')].map(itemLabel);
		expect(items).toContain("Delete plane");
	});

	it("drags a row with the plane mime and drops it into another", () => {
		render([]);
		const data = new Map<string, string>();
		const dataTransfer = {
			setData: (k: string, v: string) => data.set(k, v),
			getData: (k: string) => data.get(k) ?? "",
			effectAllowed: "",
			dropEffect: "",
		};
		const drag = (type: string, el: HTMLElement | null) => {
			const e = new Event(type, { bubbles: true, cancelable: true });
			Object.assign(e, { dataTransfer, clientY: 0 });
			act(() => {
				el?.dispatchEvent(e);
			});
		};
		expect(rowOf("b")?.getAttribute("draggable")).toBe("true");
		drag("dragstart", rowOf("b"));
		expect(JSON.parse(data.get(PLANE_MIME) ?? "")).toEqual({ plane: "b", params: {} });
		drag("dragover", rowOf("a"));
		drag("drop", rowOf("a"));
		expect(notify).toHaveBeenCalledWith("plane.move", { plane_id: "b", parent_id: "a" });
	});
});

describe("tree row tooltips", () => {
	it("drops the native title for a kit tooltip", () => {
		render([]);
		expect(host.querySelector("[title]")).toBeNull();
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

/** A menu item's own words, without the shortcut caps on its right. */
function itemLabel(item: HTMLElement): string {
	return [...item.childNodes]
		.filter((n) => n.nodeType === Node.TEXT_NODE)
		.map((n) => n.textContent)
		.join("")
		.trim();
}
