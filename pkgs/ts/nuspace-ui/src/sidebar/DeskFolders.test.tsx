// The desk folders, rendered in jsdom: the feed's order, the title folding
// and its chips (rename, close), a new desk opening its rename, item rows as
// `[icon] / [title]` with reset, open and save on hover, strips and
// column groups, close on every row kind, selection, and every drag row:
// what each row writes and the `Target` a drop on it hands to `dropOn`.
//
// jsdom lays nothing out, so a row's box is stubbed 28px tall and 200px wide
// for the drop bands: y 2 is its top quarter, 14 its middle, 26 its bottom
// quarter; x 50 its left half, 150 its right.

import { catchAnchors, tree as store, TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { applyDesksWrite, resetDesks } from "../core/desks";
import { focusedRoute, knownDesks, onReveal, resetRouter } from "../core/router";
import { ITEM_MIME, PANE_MIME, PLANE_MIME } from "../desk/dnd";
import type { Desk, Link } from "../desk/model";
import { DeskFolders, folderKeys, useFolders } from "./DeskFolders";
import {
	arrowMove,
	columnKey,
	folderRows,
	itemKey,
	paneKey,
	resetFolders,
	rowAim,
	selectedKey,
} from "./folders";
import { SidebarBody } from "./harness";
import { sidebarRule } from "./links";
import { newDesk, newDeskWith } from "./newDesk";
import { Sidebar } from "./Sidebar";
import { coerceTree, ROOT_ID } from "./types";

const dropOn = vi.hoisted(() => vi.fn());
vi.mock("../desk/dnd", async (actual) => ({
	...(await actual<typeof import("../desk/dnd")>()),
	dropOn,
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;

const L = (plane: string, params: Record<string, string> = {}): Link => ({ plane, params });

const W = "desk0001";
const F = "desk0002";

/**
 * Work: x alone; a strip of y, then z over w; p navigated to q; a strip
 * whose one pane is navigated (r to s) next to t.
 */
const WORK: Desk = {
	name: "Work",
	items: [
		{ id: "item01", kind: "plane", original: L("x") },
		{
			id: "strip1",
			kind: "strip",
			columns: [
				{ panes: [{ share: 1, original: L("y") }] },
				{
					panes: [
						{ share: 0.5, original: L("z") },
						{ share: 0.5, original: L("w") },
					],
				},
			],
		},
		{ id: "item02", kind: "plane", original: L("p"), recent: L("q", { run: "43" }) },
		{
			id: "strip2",
			kind: "strip",
			columns: [
				{ panes: [{ share: 1, original: L("r"), recent: L("s") }] },
				{ panes: [{ share: 1, original: L("t") }] },
			],
		},
	],
};
const FAV: Desk = { name: "Favorites", items: [{ id: "fav001", kind: "plane", original: L("f") }] };

const PLANES = ["x", "y", "z", "w", "p", "q", "r", "s", "t", "f"];
const tree = coerceTree([
	{ id: ROOT_ID, kind: "space", title: "", parent: ROOT_ID, children: PLANES },
	...PLANES.map((id) => ({
		id,
		kind: "plane",
		title: id.toUpperCase(),
		parent: ROOT_ID,
		children: [],
		icon: `emoji:${id}`,
	})),
]);

let host: HTMLDivElement;
let root: Root;
let release: () => void;

function feed(desks: Record<string, Desk>, order = Object.keys(desks)) {
	act(() => {
		applyDesksWrite(null, { op: "set_roles", roles: { home: "h", settings: "", search: "" } });
		applyDesksWrite(null, { op: "set_desks", desks, order });
	});
}

function Folders({ selected = null }: { selected?: string | null }) {
	const folders = useFolders();
	return (
		<SidebarBody keys={folderKeys(folders)}>
			<DeskFolders folders={folders} tree={tree} selected={selected} />
		</SidebarBody>
	);
}

function draw(selected: string | null = null) {
	act(() => {
		root.render(
			<TooltipProvider>
				<Folders selected={selected} />
			</TooltipProvider>,
		);
	});
}

beforeEach(() => {
	window.history.replaceState({}, "", "/");
	window.localStorage.clear();
	resetRouter();
	resetDesks();
	resetFolders();
	dropOn.mockClear();
	host = document.createElement("div");
	document.body.append(host);
	release = catchAnchors(host, sidebarRule);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	release();
	host.remove();
});

const folderOf = (name: string) => host.querySelector<HTMLElement>(`section[aria-label="${name}"]`);
const titleOf = (name: string) =>
	folderOf(name)?.querySelector<HTMLButtonElement>("button[aria-expanded]") ?? null;
const headOf = (name: string) => titleOf(name)?.parentElement ?? null;
const chipOf = (name: string, label: string) =>
	folderOf(name)?.querySelector<HTMLButtonElement>(`[aria-label="${label} ${name}"]`) ?? null;
const rowOf = (key: string) => host.querySelector<HTMLElement>(`[data-key="${key}"]`);
const linkOf = (key: string) => rowOf(key)?.querySelector<HTMLAnchorElement>("a") ?? null;
const names = () => [...host.querySelectorAll("section")].map((s) => s.getAttribute("aria-label"));
const keysIn = (name: string) =>
	[...(folderOf(name)?.querySelectorAll("[data-key]") ?? [])].map((r) =>
		r.getAttribute("data-key"),
	);

describe("desk folders", () => {
	it("draws the folders in the feed's order, Favorites first, no New desk row", () => {
		feed({ [W]: WORK, [F]: FAV }, [F, W]);
		draw();
		expect(names()).toEqual(["Favorites", "Work"]);
		expect(host.textContent).not.toContain("New desk");
	});

	it("shows an empty desk's body as a dashed drop line, a desk with items none", () => {
		feed({ [W]: WORK, [F]: { name: "Empty", items: [] } }, [W, F]);
		draw();
		const empty = folderOf("Empty")?.querySelector(`[data-desk-empty="${F}"]`);
		expect(empty?.textContent).toBe("Drag planes here");
		expect(folderOf("Work")?.querySelector("[data-desk-empty]")).toBeNull();
	});

	it("folds and unfolds from the title, opens nothing, never selected", () => {
		feed({ [W]: WORK });
		draw();
		act(() => titleOf("Work")?.click());
		expect(window.location.pathname).toBe("/");
		expect(keysIn("Work")).toEqual([]);
		expect(titleOf("Work")?.getAttribute("aria-expanded")).toBe("false");
		act(() => titleOf("Work")?.click());
		expect(keysIn("Work").length).toBeGreaterThan(0);
		expect(titleOf("Work")?.hasAttribute("aria-current")).toBe(false);
		expect(headOf("Work")?.className).not.toMatch(/(^|\s)bg-sidebar-a-fill/);
	});

	it("makes a desk holding a plane from newDeskWith, named Untitled, no rename open", () => {
		feed({ [W]: WORK });
		draw();
		act(() => {
			newDeskWith("q");
		});
		const made = Object.entries(knownDesks() ?? {}).find(([id]) => id !== W);
		expect(made?.[1].items).toHaveLength(1);
		expect(made?.[1].items[0]).toMatchObject({ kind: "plane", original: L("q") });
		expect(made?.[1].name).toBe("Untitled");
		expect(host.querySelector("input")).toBeNull();
		expect(window.location.pathname).toBe(`/${made?.[0]}/${made?.[1].items[0].id}`);
	});

	it("shows a New desk zone only while dragging, a drop there makes a desk of it", async () => {
		const tick = () => act(async () => await new Promise((r) => setTimeout(r)));
		feed({ [W]: WORK });
		draw();
		expect(host.querySelector("[data-new-desk]")).toBeNull();
		const held: Record<string, string> = { [PLANE_MIME]: JSON.stringify(L("q")) };
		const data = {
			types: Object.keys(held),
			getData: (k: string) => held[k] ?? "",
			dropEffect: "",
		};
		act(() => {
			window.dispatchEvent(Object.assign(new Event("dragstart"), { dataTransfer: data }));
		});
		await tick();
		const zone = host.querySelector<HTMLElement>("[data-new-desk]");
		expect(zone?.textContent).toBe("New desk");
		act(() => {
			zone?.dispatchEvent(
				Object.assign(new Event("drop", { bubbles: true, cancelable: true }), {
					dataTransfer: data,
				}),
			);
		});
		const made = Object.entries(knownDesks() ?? {}).find(([id]) => id !== W);
		expect(made?.[1].items[0]).toMatchObject({ kind: "plane", original: L("q") });
		await tick();
		expect(host.querySelector("[data-new-desk]")).toBeNull();
	});

	it("makes an empty desk named Untitled from newDesk, its folder open, no rename", () => {
		feed({ [W]: WORK });
		draw();
		act(() => {
			newDesk();
		});
		const made = Object.entries(knownDesks() ?? {}).find(([id]) => id !== W);
		expect(made?.[1]).toEqual({ name: "Untitled", items: [] });
		expect(names()).toEqual(["Work", "Untitled"]);
		expect(window.location.pathname).toBe(`/${made?.[0]}`);
		expect(host.querySelector("input")).toBeNull();
	});

	it("renames a desk in place from its title's rename", () => {
		feed({ [W]: WORK });
		draw();
		act(() => chipOf("Work", "Rename")?.click());
		const input = host.querySelector<HTMLInputElement>('input[aria-label="Rename Work"]');
		expect(input).not.toBeNull();
		act(() => {
			const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
			set?.call(input, "Research");
			input?.dispatchEvent(new Event("input", { bubbles: true }));
			input?.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
		});
		expect(knownDesks()?.[W]?.name).toBe("Research");
	});

	it("has no save on the title, only rename and close", () => {
		feed({ [W]: WORK });
		draw();
		expect(chipOf("Work", "Save")).toBeNull();
		expect(chipOf("Work", "Rename")).not.toBeNull();
		expect(chipOf("Work", "Close")).not.toBeNull();
	});

	it("saves a navigated item or pane from its row's hover save, the rest untouched", () => {
		feed({ [W]: WORK });
		draw();
		expect(rowOf(itemKey(W, "item01"))?.querySelector('[aria-label^="Save"]')).toBeNull();
		act(() =>
			rowOf(itemKey(W, "item02"))?.querySelector<HTMLElement>('[aria-label="Save Q"]')?.click(),
		);
		expect(knownDesks()?.[W]?.items[2]).toEqual({
			id: "item02",
			kind: "plane",
			original: L("q", { run: "43" }),
		});
		act(() =>
			rowOf(paneKey(W, "strip2", "s"))
				?.querySelector<HTMLElement>('[aria-label="Save S"]')
				?.click(),
		);
		const strip = knownDesks()?.[W]?.items[3];
		expect(strip?.kind === "strip" && strip.columns[0].panes[0]).toEqual({
			share: 1,
			original: L("s"),
		});
	});

	it("closes the desk from its chip, no confirm, and a tab on it goes home", () => {
		feed({ [W]: WORK, [F]: FAV });
		window.history.replaceState(null, "", `/${W}/item01`);
		draw();
		act(() => chipOf("Work", "Close")?.click());
		expect(names()).toEqual(["Favorites"]);
		expect(window.location.pathname).not.toContain(W);
		expect(document.querySelector('[role="alertdialog"]')).toBeNull();
	});
});

describe("item rows", () => {
	beforeEach(() => {
		feed({ [W]: WORK });
		draw();
	});

	it("lists items in order, a strip's panes one step in, a column of 2+ under Column", () => {
		expect(keysIn("Work")).toEqual([
			itemKey(W, "item01"),
			itemKey(W, "strip1"),
			paneKey(W, "strip1", "y"),
			columnKey(W, "strip1", 1),
			paneKey(W, "strip1", "z"),
			paneKey(W, "strip1", "w"),
			itemKey(W, "item02"),
			itemKey(W, "strip2"),
			paneKey(W, "strip2", "s"),
			paneKey(W, "strip2", "t"),
		]);
		expect(rowOf(itemKey(W, "strip1"))?.textContent).toBe("Strip");
		expect(rowOf(columnKey(W, "strip1", 1))?.textContent).toBe("Column");
		// Depths: jsdom folds the indent's calc.
		expect(rowOf(itemKey(W, "item01"))?.style.paddingLeft).toBe("calc(0.5rem)");
		expect(rowOf(paneKey(W, "strip1", "y"))?.style.paddingLeft).toBe("calc(1.75rem)");
		expect(rowOf(paneKey(W, "strip1", "z"))?.style.paddingLeft).toBe("calc(3rem)");
	});

	it("draws a plain item as icon and title, no reset", () => {
		const row = rowOf(itemKey(W, "item01"));
		expect(row?.textContent).toBe("xX");
		expect(row?.querySelector('[aria-label^="Reset"]')).toBeNull();
	});

	it("draws a navigated item as [icon] / [title]: the original's icon, the recent's title", () => {
		const row = rowOf(itemKey(W, "item02"));
		const reset = row?.querySelector<HTMLButtonElement>('[aria-label="Reset to P"]');
		expect(reset?.textContent).toBe("p");
		expect(row?.querySelector("a:not([data-sidebar-reset])")?.textContent).toBe("Q");
		expect(row?.textContent).toContain("/");
		// The pane row of a navigated pane reads the same way.
		const pane = rowOf(paneKey(W, "strip2", "s"));
		expect(pane?.querySelector('[aria-label="Reset to R"]')?.textContent).toBe("r");
		expect(pane?.querySelector("a:not([data-sidebar-reset])")?.textContent).toBe("S");
	});

	it("resets an item from its icon, and opens it from its title", () => {
		act(() =>
			rowOf(itemKey(W, "item02"))
				?.querySelector<HTMLButtonElement>('[aria-label^="Reset"]')
				?.click(),
		);
		expect(window.location.pathname).toBe("/");
		expect(knownDesks()?.[W]?.items[2]).toEqual({ id: "item02", kind: "plane", original: L("p") });
		act(() => linkOf(itemKey(W, "item01"))?.click());
		expect(window.location.pathname).toBe(`/${W}/item01`);
	});

	it("resets a navigated item from its row's hover reset too, none on a plain one", () => {
		expect(rowOf(itemKey(W, "item01"))?.querySelector('[aria-label^="Reset X"]')).toBeNull();
		act(() =>
			rowOf(itemKey(W, "item02"))
				?.querySelector<HTMLElement>('[aria-label="Reset Q to P"]')
				?.click(),
		);
		expect(knownDesks()?.[W]?.items[2]).toEqual({ id: "item02", kind: "plane", original: L("p") });
	});

	it("resets a pane from its icon", () => {
		act(() =>
			rowOf(paneKey(W, "strip2", "s"))
				?.querySelector<HTMLButtonElement>('[aria-label^="Reset"]')
				?.click(),
		);
		const strip = knownDesks()?.[W]?.items[3];
		expect(strip?.kind === "strip" && strip.columns[0].panes[0]).toEqual({
			share: 1,
			original: L("r"),
		});
	});

	it("opens a strip from its row, and a pane row opens it with that pane focused", () => {
		act(() => linkOf(itemKey(W, "strip1"))?.click());
		expect(window.location.pathname).toBe(`/${W}/strip1`);
		window.history.replaceState(null, "", "/");
		const revealed: string[] = [];
		const off = onReveal((plane) => revealed.push(plane));
		act(() => linkOf(paneKey(W, "strip1", "w"))?.click());
		off();
		expect(window.location.pathname).toBe(`/${W}/strip1`);
		expect(focusedRoute()).toBe("w");
		expect(revealed).toEqual(["w"]);
	});

	it("leaves a Cmd click on an item row to the browser", () => {
		const e = new MouseEvent("click", { bubbles: true, cancelable: true, metaKey: true });
		act(() => {
			linkOf(itemKey(W, "item01"))?.dispatchEvent(e);
		});
		expect(e.defaultPrevented).toBe(false);
		expect(window.location.pathname).toBe("/");
	});

	it("folds a strip and a column group from their chevrons", () => {
		act(() =>
			rowOf(itemKey(W, "strip1"))
				?.querySelector<HTMLButtonElement>('[aria-label="Collapse strip"]')
				?.click(),
		);
		expect(rowOf(paneKey(W, "strip1", "y"))).toBeNull();
		expect(window.location.pathname).toBe("/");
		act(() =>
			rowOf(itemKey(W, "strip1"))
				?.querySelector<HTMLButtonElement>('[aria-label="Expand strip"]')
				?.click(),
		);
		act(() =>
			rowOf(columnKey(W, "strip1", 1))
				?.querySelector<HTMLButtonElement>('[aria-label="Collapse column"]')
				?.click(),
		);
		expect(rowOf(paneKey(W, "strip1", "z"))).toBeNull();
		expect(rowOf(columnKey(W, "strip1", 1))?.getAttribute("aria-expanded")).toBe("false");
		expect(window.location.pathname).toBe("/");
	});

	it("a column group links to its strip, standing for its top pane", () => {
		const link = linkOf(columnKey(W, "strip1", 1));
		expect(link?.getAttribute("href")).toBe(`/${W}/strip1`);
		expect(link?.closest("[data-sidebar-pane]")?.getAttribute("data-sidebar-pane")).toBe("z");
	});
});

describe("close on every row", () => {
	const close = (key: string) =>
		act(() => rowOf(key)?.querySelector<HTMLButtonElement>('[aria-label^="Close"]')?.click());

	beforeEach(() => {
		feed({ [W]: WORK });
		draw();
	});

	it("an item row takes the item out", () => {
		close(itemKey(W, "item01"));
		expect(knownDesks()?.[W]?.items.map((i) => i.id)).toEqual(["strip1", "item02", "strip2"]);
	});

	it("a strip row takes the strip out", () => {
		close(itemKey(W, "strip1"));
		expect(knownDesks()?.[W]?.items.map((i) => i.id)).toEqual(["item01", "item02", "strip2"]);
	});

	it("a column group takes its column out", () => {
		close(columnKey(W, "strip1", 1));
		const strip = knownDesks()?.[W]?.items[1];
		// One pane left: the strip turned into a plane item in its place.
		expect(strip).toEqual({ id: "strip1", kind: "plane", original: L("y") });
	});

	it("a pane row takes its pane out of the strip", () => {
		close(paneKey(W, "strip1", "w"));
		const strip = knownDesks()?.[W]?.items[1];
		expect(strip?.kind === "strip" && strip.columns[1].panes.map((p) => p.original.plane)).toEqual([
			"z",
		]);
	});
});

describe("selection", () => {
	function drawSidebar() {
		const path = ["sidebar"];
		act(() => {
			store.getState().write(path.map((seg) => [seg, null]));
			store.getState().setProps(path, { loaded: true, registered: [], tree });
		});
		act(() => {
			root.render(
				<TooltipProvider>
					<Sidebar path={path} />
				</TooltipProvider>,
			);
		});
	}
	const selected = () =>
		[...host.querySelectorAll('[aria-selected="true"]')].map((r) => r.getAttribute("data-key"));

	it("a plane item: its row only, no title, nothing in the tree", () => {
		feed({ [W]: WORK });
		window.history.replaceState(null, "", `/${W}/item02`);
		drawSidebar();
		expect(selected()).toEqual([itemKey(W, "item02")]);
		expect(headOf("Work")?.className).not.toMatch(/(^|\s)bg-sidebar-a-fill/);
	});

	it("a strip: the focused pane's row", () => {
		feed({ [W]: WORK });
		drawSidebar();
		act(() => linkOf(paneKey(W, "strip1", "z"))?.click());
		expect(selected()).toEqual([paneKey(W, "strip1", "z")]);
	});

	it("solo: its tree row, nothing in the folders", () => {
		feed({ [W]: WORK });
		window.history.replaceState(null, "", "/y");
		drawSidebar();
		expect(selected()).toEqual(["y"]);
	});

	it("a tree row opens solo, even on a desk item", () => {
		feed({ [W]: WORK });
		window.history.replaceState(null, "", `/${W}/strip1`);
		drawSidebar();
		const planes = host.querySelector('section[aria-label="Planes"]');
		act(() => planes?.querySelector<HTMLAnchorElement>('[data-key="t"] a')?.click());
		expect(window.location.pathname).toBe("/t");
		// The strip was not navigated.
		expect(knownDesks()?.[W]).toEqual(WORK);
	});

	it("falls back to the nearest row still drawn while the focused one is folded away", () => {
		const strip = WORK.items[1];
		const folds = new Set([columnKey(W, "strip1", 1)]);
		expect(selectedKey(W, strip, "w", folds)).toBe(columnKey(W, "strip1", 1));
		expect(selectedKey(W, strip, "w", new Set([itemKey(W, "strip1")]))).toBe(itemKey(W, "strip1"));
		expect(selectedKey(W, strip, "w", new Set())).toBe(paneKey(W, "strip1", "w"));
		expect(selectedKey(W, WORK.items[0], "x", new Set())).toBe(itemKey(W, "item01"));
	});
});

describe("drag sources", () => {
	beforeEach(() => {
		feed({ [W]: WORK });
		draw();
	});

	function start(el: HTMLElement | null) {
		const data: Record<string, string> = {};
		const dataTransfer = {
			types: [] as string[],
			setData: (k: string, v: string) => {
				data[k] = v;
			},
			getData: (k: string) => data[k] ?? "",
			effectAllowed: "",
			dropEffect: "",
		};
		const e = new Event("dragstart", { bubbles: true, cancelable: true });
		Object.assign(e, { dataTransfer });
		act(() => {
			el?.dispatchEvent(e);
		});
		const end = new Event("dragend", { bubbles: true });
		act(() => {
			el?.dispatchEvent(end);
		});
		return data;
	}

	it("an item row writes its item, a strip row too", () => {
		expect(JSON.parse(start(rowOf(itemKey(W, "item02")))[ITEM_MIME])).toEqual({
			desk: W,
			item: "item02",
		});
		expect(JSON.parse(start(rowOf(itemKey(W, "strip1")))[ITEM_MIME])).toEqual({
			desk: W,
			item: "strip1",
		});
	});

	it("a pane row writes its pane, a column group nothing", () => {
		expect(JSON.parse(start(rowOf(paneKey(W, "strip1", "z")))[PANE_MIME])).toEqual({
			desk: W,
			item: "strip1",
			plane: "z",
		});
		expect(rowOf(columnKey(W, "strip1", 1))?.getAttribute("draggable")).toBeNull();
	});
});

describe("drop targets", () => {
	function carrying(data: Record<string, string>) {
		return {
			types: Object.keys(data),
			getData: (k: string) => data[k] ?? "",
			setData: (k: string, v: string) => {
				data[k] = v;
			},
			effectAllowed: "",
			dropEffect: "",
		};
	}

	function fire(type: string, el: HTMLElement | null, dataTransfer: object, y = 14, x = 50) {
		const e = new Event(type, { bubbles: true, cancelable: true });
		Object.assign(e, { dataTransfer, clientY: y, clientX: x });
		act(() => {
			el?.dispatchEvent(e);
		});
		return e;
	}

	function box(el: HTMLElement | null) {
		if (el)
			el.getBoundingClientRect = () => ({ top: 0, left: 0, height: 28, width: 200 }) as DOMRect;
		return el;
	}

	function dropAt(el: HTMLElement | null, data: Record<string, string>, y = 14, x = 50) {
		box(el);
		const dt = carrying(data);
		fire("dragover", el, dt, y, x);
		fire("drop", el, dt, y, x);
	}

	const plane = { [PLANE_MIME]: JSON.stringify(L("n")) };
	const PLANE = { kind: "plane", link: L("n") };
	const strip = (drop: object) => ({ kind: "strip", desk: W, item: "strip1", drop });

	beforeEach(() => {
		feed({ [W]: WORK, [F]: FAV });
		draw();
	});

	it("a folder title: the end of the desk", () => {
		dropAt(headOf("Work"), plane);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, { kind: "end", desk: W });
	});

	it("a plane item row: between items above and below, onto it in the middle by side", () => {
		const row = rowOf(itemKey(W, "item02"));
		dropAt(row, plane, 2);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, { kind: "between", desk: W, index: 2 });
		dropAt(row, plane, 26);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, { kind: "between", desk: W, index: 3 });
		dropAt(row, plane, 14, 50);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, {
			kind: "onto",
			desk: W,
			item: "item02",
			side: "left",
		});
		dropAt(row, plane, 14, 150);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, {
			kind: "onto",
			desk: W,
			item: "item02",
			side: "right",
		});
	});

	it("a strip row: between above, a last column in the middle, a first column below", () => {
		const row = rowOf(itemKey(W, "strip1"));
		dropAt(row, plane, 2);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, { kind: "between", desk: W, index: 1 });
		dropAt(row, plane, 14);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, strip({ at: 2 }));
		dropAt(row, plane, 26);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, strip({ at: 0 }));
	});

	it("a pane row and a column group: inside the strip", () => {
		const y = rowOf(paneKey(W, "strip1", "y"));
		dropAt(y, plane, 2);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, strip({ at: 0 }));
		dropAt(y, plane, 14);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, strip({ plane: "y", edge: "bottom" }));
		dropAt(y, plane, 26);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, strip({ at: 1 }));
		const group = rowOf(columnKey(W, "strip1", 1));
		dropAt(group, plane, 2);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, strip({ at: 1 }));
		dropAt(group, plane, 14);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, strip({ column: 1 }));
		dropAt(group, plane, 26);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, strip({ plane: "z", edge: "top" }));
		const w = rowOf(paneKey(W, "strip1", "w"));
		dropAt(w, plane, 2);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, strip({ plane: "w", edge: "top" }));
		dropAt(w, plane, 26);
		expect(dropOn).toHaveBeenLastCalledWith(PLANE, strip({ at: 2 }));
	});

	it("an item and a pane from another desk land as their payloads", () => {
		const item = { [ITEM_MIME]: JSON.stringify({ desk: F, item: "fav001" }) };
		dropAt(rowOf(itemKey(W, "item01")), item, 2);
		expect(dropOn).toHaveBeenLastCalledWith(
			{ kind: "item", desk: F, item: "fav001" },
			{ kind: "between", desk: W, index: 0 },
		);
		const pane = { [PANE_MIME]: JSON.stringify({ desk: W, item: "strip2", plane: "t" }) };
		dropAt(rowOf(itemKey(F, "fav001")), pane, 26);
		expect(dropOn).toHaveBeenLastCalledWith(
			{ kind: "pane", desk: W, item: "strip2", plane: "t" },
			{ kind: "between", desk: F, index: 1 },
		);
	});

	it("a strip lands only between items, nothing lands on itself", () => {
		// What lands where is the drag table's (../desk/dnd.ts `canDrop`, tested there).
		// While dragging its own row, the row offers no drop.
		const row = box(rowOf(itemKey(W, "item01")));
		const data: Record<string, string> = {};
		const dt = carrying(data);
		fire("dragstart", row, dt);
		dt.types = Object.keys(data);
		expect(fire("dragover", row, dt, 14).defaultPrevented).toBe(false);
		fire("dragend", row, dt);
	});

	it("marks between items with a line at the folder's rows, a stack two steps in", () => {
		const row = box(rowOf(itemKey(W, "item02")));
		fire("dragover", row, carrying(plane), 2);
		const line = row?.parentElement?.querySelector<HTMLElement>(":scope > span[aria-hidden]");
		// jsdom folds the calc: 0.5rem + 0 + 1.75rem.
		expect(line?.style.left).toBe("calc(2.25rem)");
		const w = box(rowOf(paneKey(W, "strip1", "w")));
		fire("dragover", w, carrying(plane), 2);
		const stack = w?.parentElement?.querySelector<HTMLElement>(":scope > span[aria-hidden]");
		expect(stack?.style.left).toBe("calc(4.75rem)");
		fire("dragover", row, carrying(plane), 14);
		expect(row?.className).toContain("ring-accent");
	});
});

describe("folder rows and aims (pure)", () => {
	it("draws a folded strip as its row only, and drops after it between items", () => {
		const rows = folderRows(W, WORK, new Set([itemKey(W, "strip1")]));
		expect(rows.map((r) => r.kind)).toEqual(["plane", "strip", "plane", "strip", "pane", "pane"]);
		expect(rowAim(W, rows[1], "after", "left").target).toEqual({
			kind: "between",
			desk: W,
			index: 2,
		});
	});
});

describe("arrows on folder rows, as on Planes tree rows", () => {
	const rows = folderRows(W, WORK, new Set());
	const at = (key: string) => rows.findIndex((r) => r.key === key);
	const move = (key: string, arrow: "ArrowLeft" | "ArrowRight") =>
		arrowMove(W, rows[at(key)], arrow, rows[at(key) + 1]);
	const strip = itemKey(W, "strip1");
	const column = columnKey(W, "strip1", 1);

	it("steps into an open strip or column, and unfolds a folded one", () => {
		expect(move(strip, "ArrowRight")).toEqual({ focus: paneKey(W, "strip1", "y") });
		expect(move(column, "ArrowRight")).toEqual({ focus: paneKey(W, "strip1", "z") });
		const folded = folderRows(W, WORK, new Set([strip]));
		expect(arrowMove(W, folded[1], "ArrowRight", folded[2])).toEqual({ fold: true });
	});

	it("folds an open strip or column, and climbs from a folded column to its strip", () => {
		expect(move(strip, "ArrowLeft")).toEqual({ fold: true });
		expect(move(column, "ArrowLeft")).toEqual({ fold: true });
		const folded = folderRows(W, WORK, new Set([column]));
		const c = folded.find((r) => r.key === column);
		expect(c && arrowMove(W, c, "ArrowLeft", undefined)).toEqual({ focus: strip });
	});

	it("climbs from a pane to its strip or column group, and does nothing on Right", () => {
		expect(move(paneKey(W, "strip1", "y"), "ArrowLeft")).toEqual({ focus: strip });
		expect(move(paneKey(W, "strip1", "z"), "ArrowLeft")).toEqual({ focus: column });
		expect(move(paneKey(W, "strip1", "y"), "ArrowRight")).toBeNull();
	});

	it("does nothing on a top level plane item, nor Left on a folded strip", () => {
		expect(move(itemKey(W, "item01"), "ArrowLeft")).toBeNull();
		expect(move(itemKey(W, "item01"), "ArrowRight")).toBeNull();
		const folded = folderRows(W, WORK, new Set([strip]));
		expect(arrowMove(W, folded[1], "ArrowLeft", folded[2])).toBeNull();
	});
});
