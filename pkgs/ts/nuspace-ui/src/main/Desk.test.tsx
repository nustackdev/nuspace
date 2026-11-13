// The canvas drawn in jsdom, one view per route: a strip (one row of columns
// at their px width, the end zone, panes by share), a plane item, a solo
// plane, the empty desk, pending and not found. Click focus, reveal, close per
// view, links navigating in place through the router, `planes.open` getting
// the shown planes, resizing, the plane list fed to the router, each drop
// target through `dropOn`, and what a pane header's drag carries per view.

import { catchAnchors, TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { applyDesksWrite, resetDesks } from "../core/desks";
import * as router from "../core/router";
import { notifyOp } from "../core/wire";
import * as dnd from "../desk/dnd";
import {
	type Desk as DeskShape,
	type Item,
	type Link,
	locate,
	MIN_WIDTH,
	type PlaneItem,
	type Strip,
	shownLinks,
} from "../desk/model";
import { NOT_FOUND_TEXT } from "../pane/NotFound";
import type { Ops } from "../plane/ops";
import { usePlaneTree } from "../sidebar/api";
import { Desk, EMPTY_DESK, EMPTY_DESK_HINT } from "./Desk";
import { useTrails } from "./state";

const { currentRoute, focusPane, onDeskWrite, openPane, paneRule, resetRouter } = router;
const { ITEM_MIME, PANE_MIME, PLANE_MIME } = dnd;

vi.mock("../core/wire", () => ({ notifyOp: vi.fn() }));
// The trails the viewer feed ships: none unless a test says.
vi.mock("./state", async (real) => ({
	...(await real<typeof import("./state")>()),
	useTrails: vi.fn(() => ({})),
}));
// The sidebar's tree and delete: not what is tested here.
vi.mock("../sidebar/api", () => ({
	usePlaneTree: vi.fn(() => ({})),
	canDelete: () => false,
	deletePlane: vi.fn(),
	deskLabel: (name: string) => name.trim() || "Desk",
	STRIP_TITLE: "Strip",
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;

const ID = "desk0001";
const OTHER = "desk0002";
const EMPTY = "desk0003";
const VIEWER = ["shell", "viewer"];

const link = (plane: string, params: Record<string, string> = {}): Link => ({ plane, params });
const pane = (plane: string, share = 1, params: Record<string, string> = {}) => ({
	share,
	original: link(plane, params),
});

/** A strip: [a | b over c | d]. */
const STRIP: Strip = {
	id: "strip1",
	kind: "strip",
	columns: [
		{ width: 600, panes: [pane("a", 1, { q: "1" })] },
		{ panes: [pane("b", 0.75), pane("c", 0.25)] },
		{ width: 900, panes: [pane("d")] },
	],
};

/** A plane item saved on `e`, navigated to `f`. */
const LONE: PlaneItem = {
	id: "lone01",
	kind: "plane",
	original: link("e"),
	recent: link("f", { run: "43" }),
};

const WORK: DeskShape = { name: "Work", items: [STRIP, LONE] };

/** Another desk: a strip of x and y, and a plane item on w. */
const ELSEWHERE: DeskShape = {
	name: "Other",
	items: [
		{
			id: "other1",
			kind: "strip",
			columns: [{ panes: [pane("x")] }, { panes: [pane("y")] }],
		},
		{ id: "other2", kind: "plane", original: link("w") },
	],
};

const STRIP_URL = `/${ID}/strip1`;
const LONE_URL = `/${ID}/lone01`;

let host: HTMLDivElement;
let root: Root;

function feed(desks: Record<string, DeskShape>) {
	act(() => {
		applyDesksWrite(["shell", "desks"], { op: "set_desks", desks, order: Object.keys(desks) });
		applyDesksWrite(["shell", "desks"], {
			op: "set_roles",
			roles: { home: "", settings: "", search: "" },
		});
	});
}

const DESKS = { [ID]: WORK, [OTHER]: ELSEWHERE, [EMPTY]: { name: "Empty", items: [] } };

function draw(path: string) {
	window.history.replaceState(null, "", path);
	act(() => {
		root.render(
			<TooltipProvider>
				<Desk path={VIEWER} />
			</TooltipProvider>,
		);
	});
}

const all = (sel: string) => [...host.querySelectorAll<HTMLElement>(sel)];
const one = (sel: string) => host.querySelector(sel) as HTMLElement;
/** Close the pane showing `plane` from its `...` menu (its header's X closes it too). */
function closeFromMenu(plane: string) {
	const trigger = one(`[data-pane="${plane}"] [aria-label="Plane settings"]`);
	act(() => {
		trigger.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
	});
	const close = [...document.querySelectorAll<HTMLElement>('[role="menuitem"]')].find(
		(i) => i.textContent?.trim() === "Close",
	);
	if (!close) throw new Error("no Close in the pane menu");
	act(() => close.click());
}
const opened = () =>
	vi
		.mocked(notifyOp)
		.mock.calls.filter(([, op]) => op === "planes.open")
		.map(([, , args]) => args as Ops["planes.open"]);

/** The item the canvas shows, from the route. */
function shownItem(): Item {
	const route = currentRoute();
	if (route.kind !== "item") throw new Error(`not on an item: ${route.kind}`);
	return route.item;
}

beforeEach(() => {
	resetRouter();
	resetDesks();
	vi.mocked(notifyOp).mockClear();
	vi.mocked(usePlaneTree).mockImplementation(() => ({}));
	vi.mocked(useTrails).mockImplementation(() => ({}));
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
	vi.restoreAllMocks();
});

describe("a strip", () => {
	it("draws one row of columns and nothing after them", () => {
		feed(DESKS);
		draw(STRIP_URL);
		const row = one(`[data-desk="${ID}"]`);
		expect(row.dataset.item).toBe("strip1");
		expect(row.getAttribute("data-orientation")).toBe("horizontal");
		const columns = all("[data-column]");
		expect(columns).toHaveLength(3);
		expect(new Set(columns.map((c) => c.parentElement))).toEqual(
			new Set([columns[0].parentElement]),
		);
		expect(columns[0].parentElement?.lastElementChild).toBe(columns[2]);
	});

	it("draws columns side by side, panes stacked by share", () => {
		feed(DESKS);
		draw(STRIP_URL);
		const columns = all("[data-column]");
		expect(columns[0].style.width).toBe("600px");
		expect(columns[2].style.width).toBe("900px");
		const shares = [...columns[1].querySelectorAll<HTMLElement>("[data-share]")];
		expect(shares.map((s) => s.style.flexGrow)).toEqual(["0.75", "0.25"]);
		expect(shares.map((s) => s.querySelector("[data-pane]")?.getAttribute("data-pane"))).toEqual([
			"b",
			"c",
		]);
	});

	it("draws each pane's shown plane: its recent, else its original", () => {
		const navigated: DeskShape = {
			...WORK,
			items: [
				{
					...STRIP,
					columns: [
						{ panes: [{ share: 1, original: link("a"), recent: link("g") }] },
						STRIP.columns[1],
					],
				},
				LONE,
			],
		};
		feed({ [ID]: navigated });
		draw(STRIP_URL);
		expect(all("[data-pane]").map((p) => p.dataset.pane)).toEqual(["g", "b", "c"]);
	});

	it("gives each pane a header to drag by, with a close and a menu", () => {
		feed(DESKS);
		draw(STRIP_URL);
		expect(all("[data-pane-header]").map((h) => h.dataset.paneHeader)).toEqual([
			"a",
			"b",
			"c",
			"d",
		]);
		expect(all('[data-pane] [data-pane-header] [aria-label^="Close "]')).toHaveLength(4);
		expect(all('[data-pane] [aria-label="Plane settings"]')).toHaveLength(4);
	});

	it("focuses a pane on a click, per tab, its title bright and the others dimmed", () => {
		const writes = vi.fn();
		const off = onDeskWrite(writes);
		feed(DESKS);
		draw(STRIP_URL);
		act(() => {
			one('[data-pane="c"]').dispatchEvent(new MouseEvent("pointerdown", { bubbles: true }));
		});
		expect(all("[data-focused]").map((p) => p.dataset.pane)).toEqual(["c"]);
		const title = (id: string) =>
			host.querySelector(`[data-pane-header="${id}"] span.truncate`)?.className ?? "";
		expect(title("c")).toContain("text-text-primary");
		expect(title("a")).toContain("text-text-muted");
		expect(writes).not.toHaveBeenCalled();
		off();
	});

	it("does not move focus when a pane only takes DOM focus", () => {
		feed(DESKS);
		draw(STRIP_URL);
		act(() => focusPane(ID, "strip1", "a"));
		act(() => {
			one('[data-pane="d"]').dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
		});
		expect(all("[data-focused]").map((p) => p.dataset.pane)).toEqual(["a"]);
	});

	it("closes a pane out of the strip", () => {
		const closePane = vi.spyOn(router, "closePane");
		feed(DESKS);
		draw(STRIP_URL);
		closeFromMenu("a");
		expect(closePane).toHaveBeenCalledWith(ID, "strip1", "a");
		expect(all("[data-pane]").map((p) => p.dataset.pane)).toEqual(["b", "c", "d"]);
	});

	it("closes a pane by its header's X too", () => {
		const closePane = vi.spyOn(router, "closePane");
		feed(DESKS);
		draw(STRIP_URL);
		const x = one('[data-pane="b"] [data-pane-header] button[aria-label^="Close "]');
		act(() => x.click());
		expect(closePane).toHaveBeenCalledWith(ID, "strip1", "b");
		expect(all("[data-pane]").map((p) => p.dataset.pane)).toEqual(["a", "c", "d"]);
	});

	describe("scrolling a pane into view", () => {
		// jsdom has no scrollIntoView: record who asks for it.
		let shown: { id: string; behavior: string }[];
		beforeEach(() => {
			shown = [];
			HTMLElement.prototype.scrollIntoView = function (this: HTMLElement, arg?: unknown) {
				const opts = (arg ?? {}) as ScrollIntoViewOptions;
				shown.push({ id: this.dataset.pane ?? "", behavior: opts.behavior ?? "" });
			};
		});
		afterEach(() => {
			delete (HTMLElement.prototype as Partial<HTMLElement>).scrollIntoView;
		});

		it("follows the focused pane when its place changes, the focus unchanged", () => {
			feed(DESKS);
			draw(STRIP_URL);
			act(() => focusPane(ID, "strip1", "a"));
			shown = [];
			act(() =>
				dnd.dropOn(
					{ kind: "pane", desk: ID, item: "strip1", plane: "a" },
					{ kind: "strip", desk: ID, item: "strip1", drop: { plane: "b", edge: "right" } },
				),
			);
			const item = shownItem();
			expect(item.kind === "strip" && locate(item, "a")).toEqual({ column: 1, pane: 0 });
			expect(shown.map((s) => s.id)).toContain("a");
		});

		it("reveals a pane a sidebar row opens, in this strip or another", () => {
			feed(DESKS);
			draw(STRIP_URL);
			shown = [];
			act(() => openPane(ID, "strip1", "d"));
			expect(shown.at(-1)?.id).toBe("d");
			act(() => openPane(OTHER, "other1", "y"));
			const route = currentRoute();
			expect(route.kind === "item" && [route.desk, route.item.id]).toEqual([OTHER, "other1"]);
			expect(host.querySelector(`[data-desk="${OTHER}"]`)).not.toBeNull();
			expect(shown.at(-1)?.id).toBe("y");
		});
	});
});

describe("a plane item", () => {
	it("draws its shown plane alone, full size, with no row", () => {
		feed(DESKS);
		draw(LONE_URL);
		expect(all("[data-pane]").map((p) => p.dataset.pane)).toEqual(["f"]);
		expect(all("[data-column]")).toEqual([]);
		expect(one(`[data-desk="${ID}"]`).dataset.item).toBe("lone01");
		expect(all("[data-focused]")).toHaveLength(1);
	});

	it("closes the item out of its desk", () => {
		const closeItem = vi.spyOn(router, "closeItem");
		feed(DESKS);
		draw(LONE_URL);
		closeFromMenu("f");
		expect(closeItem).toHaveBeenCalledWith(ID, "lone01");
	});
});

describe("the desk header", () => {
	const header = () => host.querySelector<HTMLElement>("[data-desk-header]");

	it("names the desk and lists none of its items: the sidebar has them", () => {
		feed(DESKS);
		draw(STRIP_URL);
		expect(header()?.dataset.deskHeader).toBe(ID);
		expect(header()?.textContent).toContain("Work");
		expect(header()?.querySelectorAll("a")).toHaveLength(0);
	});

	it("is there on an empty desk", () => {
		feed(DESKS);
		draw(`/${EMPTY}`);
		expect(header()?.textContent).toContain("Empty");
	});

	it("is not on a solo plane", () => {
		feed(DESKS);
		draw("/p_one");
		expect(header()).toBeNull();
	});

	it("closes the desk by leaving it for home, the desk kept", () => {
		const closeDesk = vi.spyOn(router, "closeDesk");
		feed(DESKS);
		draw(STRIP_URL);
		expect(header()?.querySelector('[aria-label^="Rename"]')).toBeNull();
		act(() => one('[data-desk-header] [aria-label="Close Work"]').click());
		expect(closeDesk).not.toHaveBeenCalled();
		expect(window.location.pathname).toBe("/");
		expect(header()).toBeNull();
	});
});

describe("solo, the empty desk, pending and not found", () => {
	it("draws a solo plane as one pane, no row, no close", () => {
		feed(DESKS);
		draw("/p_one");
		expect(all("[data-pane]").map((p) => p.dataset.pane)).toEqual(["p_one"]);
		expect(all("[data-column]")).toEqual([]);
		expect(host.querySelector('[aria-label^="Close"]')).toBeNull();
		expect(all("[data-focused]")).toHaveLength(1);
	});

	it("draws an empty desk as the kit's empty state with a hint to drag a plane in", () => {
		feed(DESKS);
		draw(`/${EMPTY}`);
		expect(currentRoute().kind).toBe("desk");
		expect(host.querySelector("[data-pane]")).toBeNull();
		const empty = one('[data-slot="empty-state"]');
		expect(empty.textContent).toContain(EMPTY_DESK);
		expect(empty.textContent).toContain(EMPTY_DESK_HINT);
	});

	it("waits with a spinner until the desks and the roles land", () => {
		draw(STRIP_URL);
		expect(currentRoute().kind).toBe("pending");
		expect(host.querySelector("[data-pane]")).toBeNull();
		expect(host.querySelector('[data-slot="empty-state"]')).not.toBeNull();
	});

	it("draws a not found pane for a path that is no plane, desk or item url", () => {
		feed(DESKS);
		draw("/a/b/c");
		const pane = host.querySelector('section[data-not-found="page"]');
		expect(pane?.querySelector("header")).toBeNull();
		expect(pane?.textContent).toContain(NOT_FOUND_TEXT.page);
		expect(pane?.querySelector("a")?.textContent).toBe("Go home");
	});

	it("draws a not found pane for an unknown desk and a known desk's unknown item", () => {
		feed(DESKS);
		draw(`/zzzzzzzz/${LONE.id}`);
		expect(host.querySelector('section[data-not-found="desk"]')?.textContent).toContain(
			NOT_FOUND_TEXT.desk,
		);
		draw(`/${ID}/zzzzzz`);
		expect(host.querySelector('section[data-not-found="item"]')?.textContent).toContain(
			NOT_FOUND_TEXT.item,
		);
	});
});

describe("links inside the canvas", () => {
	let release: () => void;
	beforeEach(() => {
		release = catchAnchors(host, paneRule);
		// Every pane has the one parent.
		const trail = [{ id: "par", title: "Parent" }];
		vi.mocked(useTrails).mockImplementation(() => new Proxy({}, { get: () => trail }));
	});
	afterEach(() => release());

	const follow = (inPane: string) =>
		act(() =>
			(host.querySelector(`[data-pane="${inPane}"] a[href="/par"]`) as HTMLElement).click(),
		);

	it("navigate the pane they are in, in place, writing its recent", () => {
		const writes: DeskShape[] = [];
		const off = onDeskWrite((_, desk) => writes.push(desk));
		feed(DESKS);
		draw(STRIP_URL);
		follow("c");
		expect(window.location.pathname).toBe(STRIP_URL);
		expect(writes).toHaveLength(1);
		expect(shownLinks(shownItem()).map((l) => l.plane)).toEqual(["a", "b", "par", "d"]);
		expect(all("[data-pane]").map((p) => p.dataset.pane)).toEqual(["a", "b", "par", "d"]);
		off();
	});

	it("navigate a plane item in place, writing its recent", () => {
		feed(DESKS);
		draw(LONE_URL);
		follow("f");
		expect(window.location.pathname).toBe(LONE_URL);
		const item = shownItem();
		expect(item.kind === "plane" && item.recent).toEqual(link("par"));
		expect(all("[data-pane]").map((p) => p.dataset.pane)).toEqual(["par"]);
	});

	it("just move the url on a solo plane", () => {
		const writes = vi.fn();
		const off = onDeskWrite(writes);
		feed(DESKS);
		draw("/p_one");
		follow("p_one");
		expect(window.location.pathname).toBe("/par");
		expect(writes).not.toHaveBeenCalled();
		off();
	});
});

describe("planes.open", () => {
	it("gets the strip's shown planes in order with their params, and again when the feed changes them", () => {
		feed(DESKS);
		draw(STRIP_URL);
		expect(opened().at(-1)).toEqual({
			plane_ids: ["a", "b", "c", "d"],
			params: { a: { q: "1" }, b: {}, c: {}, d: {} },
		});
		// Another tab's write, through the feed: this tab follows it.
		const moved: Item = { ...STRIP, columns: [STRIP.columns[2], ...STRIP.columns.slice(0, 2)] };
		feed({ ...DESKS, [ID]: { ...WORK, items: [moved, LONE] } });
		expect(all("[data-pane]").map((p) => p.dataset.pane)).toEqual(["d", "a", "b", "c"]);
		expect(opened().at(-1)?.plane_ids).toEqual(["d", "a", "b", "c"]);
	});

	it("gets a plane item's shown plane and its params", () => {
		feed(DESKS);
		draw(LONE_URL);
		expect(opened().at(-1)).toEqual({ plane_ids: ["f"], params: { f: { run: "43" } } });
	});

	it("sends nothing on a focus move", () => {
		feed(DESKS);
		draw(STRIP_URL);
		const before = opened().length;
		act(() => focusPane(ID, "strip1", "d"));
		expect(opened()).toHaveLength(before);
	});
});

describe("resizing", () => {
	let writes: DeskShape[];
	let off: () => void;
	const size = (key: "clientWidth" | "clientHeight" | "offsetWidth", px: number) =>
		Object.defineProperty(HTMLElement.prototype, key, { configurable: true, get: () => px });

	beforeEach(() => {
		writes = [];
		off = onDeskWrite((_, desk) => writes.push(desk));
		size("clientWidth", 1206);
		size("clientHeight", 606);
		size("offsetWidth", 600);
	});

	afterEach(() => {
		off();
		delete (HTMLElement.prototype as { clientWidth?: number }).clientWidth;
		delete (HTMLElement.prototype as { clientHeight?: number }).clientHeight;
		delete (HTMLElement.prototype as { offsetWidth?: number }).offsetWidth;
	});

	const pointer = (target: EventTarget, type: string, at: { clientX?: number; clientY?: number }) =>
		act(() => {
			target.dispatchEvent(new MouseEvent(type, { bubbles: true, button: 0, ...at }));
		});

	const handles = () => all("[data-column] > [aria-hidden]:not(span)");
	const stripOf = (desk: DeskShape) => desk.items[0] as Strip;

	it("previews a column width from the width drawn and writes its px once, clamped, on release", () => {
		feed(DESKS);
		draw(STRIP_URL);
		const column = all("[data-column]")[0];
		expect(column.style.width).toBe("600px");
		const handle = handles()[0];
		pointer(handle, "pointerdown", { clientX: 600 });
		pointer(window, "pointermove", { clientX: 650 });
		expect(column.style.width).toBe("650px");
		pointer(window, "pointermove", { clientX: 5000 });
		expect(column.style.width).toBe("1200px");
		pointer(window, "pointermove", { clientX: 100 });
		expect(column.style.width).toBe(`${MIN_WIDTH}px`);
		expect(writes).toHaveLength(0);
		pointer(window, "pointerup", { clientX: 100 });
		expect(writes).toHaveLength(1);
		expect(stripOf(writes[0]).columns[0].width).toBe(MIN_WIDTH);
		expect(all("[data-column]")[0].style.width).toBe(`${MIN_WIDTH}px`);
	});

	it("writes a column's shares once on release", () => {
		feed(DESKS);
		draw(STRIP_URL);
		const column = all("[data-column]")[1];
		const share = column.querySelector("[data-share]") as HTMLElement;
		const handle = share.querySelector(":scope > [aria-hidden]:not(span)") as HTMLElement;
		pointer(handle, "pointerdown", { clientY: 300 });
		pointer(window, "pointermove", { clientY: 240 });
		pointer(window, "pointermove", { clientY: 270 });
		expect(writes).toHaveLength(0);
		pointer(window, "pointerup", { clientY: 270 });
		expect(writes).toHaveLength(1);
		const [b, c] = stripOf(writes[0]).columns[1].panes;
		expect(b.share).toBeCloseTo(0.7, 9);
		expect(c.share).toBeCloseTo(0.3, 9);
	});

	it("writes nothing for a press that never travels", () => {
		feed(DESKS);
		draw(STRIP_URL);
		const handle = handles()[0];
		pointer(handle, "pointerdown", { clientX: 600 });
		pointer(window, "pointerup", { clientX: 600 });
		expect(writes).toHaveLength(0);
	});
});

describe("the plane list", () => {
	it("tells the router which planes exist once the tree lands, so a short id resolves", () => {
		const setPlanes = vi.spyOn(router, "setPlanes");
		feed({});
		draw("/abcd1234");
		expect(currentRoute().kind).toBe("pending");
		expect(setPlanes).toHaveBeenLastCalledWith(null);
		const row = { id: "abcd1234", title: "Logs", parent: "abcd1234", children: [] };
		vi.mocked(usePlaneTree).mockImplementation(() => ({ abcd1234: row }) as never);
		draw("/abcd1234");
		expect(setPlanes).toHaveBeenLastCalledWith(["abcd1234"]);
		expect(currentRoute().kind).toBe("solo");
	});
});

describe("dropping", () => {
	/** A drag event carrying `payload` under `mime`, as the browser hands it to the canvas. */
	function drag(
		target: Element,
		type: "dragover" | "drop",
		mime: string,
		payload: string,
		x: number,
		y: number,
	) {
		const event = new Event(type, { bubbles: true, cancelable: true });
		Object.assign(event, {
			clientX: x,
			clientY: y,
			dataTransfer: {
				types: [mime],
				getData: (m: string) => (m === mime && type === "drop" ? payload : ""),
				dropEffect: "none",
			},
		});
		act(() => {
			target.dispatchEvent(event);
		});
		return event;
	}

	const rect = (el: Element) => {
		(el as HTMLElement).getBoundingClientRect = () =>
			({ left: 0, top: 0, width: 400, height: 200 }) as DOMRect;
	};

	const plane = (id: string) => JSON.stringify(link(id));

	afterEach(() => dnd.endDrag());

	it("in a strip: a pane's edge as a new column there, drawn as its region", () => {
		const dropOn = vi.spyOn(dnd, "dropOn");
		feed(DESKS);
		draw(STRIP_URL);
		const c = one('[data-pane="c"]');
		rect(c);
		const over = drag(c, "dragover", PLANE_MIME, "", 380, 100);
		expect(over.defaultPrevented).toBe(true);
		expect(one("[data-drop-region]").textContent).toBe("New column");
		drag(c, "drop", PLANE_MIME, plane("z"), 380, 100);
		expect(dropOn).toHaveBeenCalledWith(
			{ kind: "plane", link: link("z") },
			{ kind: "strip", desk: ID, item: "strip1", drop: { plane: "c", edge: "right" } },
		);
		const item = shownItem();
		expect(item.kind === "strip" && locate(item, "z")).toEqual({ column: 2, pane: 0 });
		expect(host.querySelector("[data-drop-region]")).toBeNull();
	});

	it("in a strip: a pane's half as stacked there, for a pane from another desk", () => {
		const dropOn = vi.spyOn(dnd, "dropOn");
		feed(DESKS);
		draw(STRIP_URL);
		const a = one('[data-pane="a"]');
		rect(a);
		const payload = JSON.stringify({ desk: OTHER, item: "other1", plane: "x" });
		drag(a, "dragover", PANE_MIME, payload, 200, 150);
		expect(one("[data-drop-region]").textContent).toBe("Stack below");
		drag(a, "drop", PANE_MIME, payload, 200, 150);
		expect(dropOn).toHaveBeenCalledWith(
			{ kind: "pane", desk: OTHER, item: "other1", plane: "x" },
			{ kind: "strip", desk: ID, item: "strip1", drop: { plane: "a", edge: "bottom" } },
		);
		const item = shownItem();
		expect(item.kind === "strip" && locate(item, "x")).toEqual({ column: 0, pane: 1 });
	});

	it("in a strip: nothing off the panes, the last pane's right edge is the end", () => {
		const dropOn = vi.spyOn(dnd, "dropOn");
		feed(DESKS);
		draw(STRIP_URL);
		const columns = one("[data-column]").parentElement as Element;
		expect(drag(columns, "dragover", ITEM_MIME, "", 10, 10).defaultPrevented).toBe(false);
		const d = one('[data-pane="d"]');
		rect(d);
		drag(d, "dragover", ITEM_MIME, "", 390, 100);
		const payload = JSON.stringify({ desk: OTHER, item: "other2" });
		drag(d, "drop", ITEM_MIME, payload, 390, 100);
		expect(dropOn).toHaveBeenCalledWith(
			{ kind: "item", desk: OTHER, item: "other2" },
			{ kind: "strip", desk: ID, item: "strip1", drop: { plane: "d", edge: "right" } },
		);
		expect(shownLinks(shownItem()).map((l) => l.plane)).toEqual(["a", "b", "c", "d", "w"]);
	});

	it("on a plane item: its left or right edge, the two made a strip", () => {
		const dropOn = vi.spyOn(dnd, "dropOn");
		feed(DESKS);
		draw(LONE_URL);
		const f = one('[data-pane="f"]');
		rect(f);
		drag(f, "dragover", PLANE_MIME, "", 20, 100);
		expect(one("[data-drop-region]").textContent).toBe("Side by side");
		drag(f, "drop", PLANE_MIME, plane("z"), 20, 100);
		expect(dropOn).toHaveBeenCalledWith(
			{ kind: "plane", link: link("z") },
			{ kind: "onto", desk: ID, item: "lone01", edge: "left" },
		);
		const item = shownItem();
		expect(item.kind).toBe("strip");
		expect(shownLinks(item).map((l) => l.plane)).toEqual(["z", "f"]);
	});

	it("on a plane item: its middle stacks the two in one column", () => {
		const dropOn = vi.spyOn(dnd, "dropOn");
		feed(DESKS);
		draw(LONE_URL);
		const f = one('[data-pane="f"]');
		rect(f);
		const over = drag(f, "dragover", PLANE_MIME, "", 200, 20);
		expect(over.defaultPrevented).toBe(true);
		expect(one("[data-drop-region]").textContent).toBe("Stack above");
		drag(f, "drop", PLANE_MIME, plane("z"), 200, 20);
		expect(dropOn).toHaveBeenCalledWith(
			{ kind: "plane", link: link("z") },
			{ kind: "onto", desk: ID, item: "lone01", edge: "top" },
		);
		const item = shownItem();
		expect(item.kind === "strip" && item.columns.length).toBe(1);
		expect(shownLinks(item).map((l) => l.plane)).toEqual(["z", "f"]);
	});

	it("on a plane item: the right edge for an item", () => {
		const dropOn = vi.spyOn(dnd, "dropOn");
		feed(DESKS);
		draw(LONE_URL);
		const f = one('[data-pane="f"]');
		rect(f);
		const payload = JSON.stringify({ desk: OTHER, item: "other2" });
		drag(f, "dragover", ITEM_MIME, "", 390, 100);
		drag(f, "drop", ITEM_MIME, payload, 390, 100);
		expect(dropOn).toHaveBeenCalledWith(
			{ kind: "item", desk: OTHER, item: "other2" },
			{ kind: "onto", desk: ID, item: "lone01", edge: "right" },
		);
	});

	it("on an empty desk: anywhere, the end of the desk, drawn as the whole desk", () => {
		const dropOn = vi.spyOn(dnd, "dropOn");
		feed(DESKS);
		draw(`/${EMPTY}`);
		const area = one(`[data-desk="${EMPTY}"]`);
		const over = drag(area.firstElementChild as Element, "dragover", PLANE_MIME, "", 5, 5);
		expect(over.defaultPrevented).toBe(true);
		expect(area.querySelector("span.bg-doc-drop")).not.toBeNull();
		expect(one("[data-drop-region]").textContent).toBe("Pin");
		drag(area, "drop", PLANE_MIME, plane("z"), 5, 5);
		expect(dropOn).toHaveBeenCalledWith(
			{ kind: "plane", link: link("z") },
			{ kind: "end", desk: EMPTY },
		);
		expect(window.location.pathname).toBe(`/${EMPTY}`);
		expect(area.querySelector("span.bg-doc-drop")).toBeNull();
	});

	it("in a strip: a plane it shows already is refused, the pane saying so", () => {
		const dropOn = vi.spyOn(dnd, "dropOn");
		feed(DESKS);
		draw(STRIP_URL);
		const c = one('[data-pane="c"]');
		rect(c);
		// The drag as the page starts it, so the table knows the plane.
		dnd.writePlane({ setData() {} } as unknown as DataTransfer, "a");
		const over = drag(c, "dragover", PLANE_MIME, "", 380, 100);
		expect(over.defaultPrevented).toBe(false);
		const region = one("[data-drop-region]");
		expect(region.hasAttribute("data-refused")).toBe(true);
		expect(region.textContent).toBe("Already in strip");
		drag(c, "drop", PLANE_MIME, plane("a"), 380, 100);
		expect(dropOn).not.toHaveBeenCalled();
	});

	it("on a solo plane: its left or right edge, a new desk of the two", () => {
		const dropOnSolo = vi.spyOn(dnd, "dropOnSolo");
		feed(DESKS);
		draw("/p_one");
		const p = one('[data-pane="p_one"]');
		rect(p);
		const over = drag(p, "dragover", PLANE_MIME, "", 10, 100);
		expect(over.defaultPrevented).toBe(true);
		drag(p, "drop", PLANE_MIME, plane("z"), 10, 100);
		expect(dropOnSolo).toHaveBeenCalledWith(
			{ kind: "plane", link: link("z") },
			{ plane: "p_one", params: {} },
			"left",
		);
	});

	describe("a pane header's drag", () => {
		function start(header: HTMLElement) {
			const data: Record<string, string> = {};
			const event = new Event("dragstart", { bubbles: true });
			Object.assign(event, {
				dataTransfer: { effectAllowed: "none", setData: (m: string, v: string) => (data[m] = v) },
			});
			act(() => {
				header.dispatchEvent(event);
			});
			return data;
		}

		it("in a strip carries the pane, and offers no drop onto itself", () => {
			feed(DESKS);
			draw(STRIP_URL);
			const data = start(one('[data-pane-header="b"]'));
			expect(Object.keys(data)).toEqual([PANE_MIME]);
			expect(JSON.parse(data[PANE_MIME])).toEqual({ desk: ID, item: "strip1", plane: "b" });
			const b = one('[data-pane="b"]');
			rect(b);
			const over = drag(b, "dragover", PANE_MIME, "", 10, 100);
			expect(over.defaultPrevented).toBe(false);
			expect(host.querySelector("[data-drop-region]")).toBeNull();
		});

		it("on a plane item carries the item, and offers no drop onto itself", () => {
			feed(DESKS);
			draw(LONE_URL);
			const data = start(one('[data-pane-header="f"]'));
			expect(Object.keys(data)).toEqual([ITEM_MIME]);
			expect(JSON.parse(data[ITEM_MIME])).toEqual({ desk: ID, item: "lone01" });
			const f = one('[data-pane="f"]');
			rect(f);
			const over = drag(f, "dragover", ITEM_MIME, "", 10, 100);
			expect(over.defaultPrevented).toBe(false);
		});

		it("on a solo plane carries the plane with the params it shows", () => {
			feed(DESKS);
			draw("/p_one?run=42");
			const data = start(one('[data-pane-header="p_one"]'));
			expect(Object.keys(data)).toEqual([PLANE_MIME]);
			expect(JSON.parse(data[PLANE_MIME])).toEqual(link("p_one", { run: "42" }));
		});
	});
});
