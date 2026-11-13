// A pane body's scroll, driven off its node: follow pins the body to its end
// as it grows, the user scrolling up pauses it and coming back resumes it,
// and a one shot command applies once per seq, a replay or a remount moving
// nothing. Rendered through the real Pane, with jsdom's missing layout faked
// on the viewport: its heights and scrollTop, and the ResizeObserver.

import { TooltipProvider, tree } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { Pane } from "./Pane";
import { applyScroll, coerceScroll } from "./scroll";
import { applyPaneWrite, panePath } from "./state";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// Every observer made, so a test can say "the content grew".
const observers: FakeObserver[] = [];
class FakeObserver {
	targets = new Set<Element>();
	readonly cb: ResizeObserverCallback;
	constructor(cb: ResizeObserverCallback) {
		this.cb = cb;
		observers.push(this);
	}
	observe(el: Element) {
		this.targets.add(el);
	}
	unobserve(el: Element) {
		this.targets.delete(el);
	}
	disconnect() {
		this.targets.clear();
	}
	fire() {
		if (this.targets.size) this.cb([], this as unknown as ResizeObserver);
	}
}
globalThis.ResizeObserver = FakeObserver as unknown as typeof ResizeObserver;

/** The content grew (or shrank): every live observer hears it. */
function grow(to: number) {
	box.height = to;
	act(() => {
		for (const o of [...observers]) o.fire();
	});
}

// The viewport's layout, faked: 100 tall, content `box.height` tall.
const box = { height: 100, top: 0 };

function viewport(): HTMLElement {
	return host.querySelector("[data-slot=scroll-area-viewport]") as HTMLElement;
}

function fakeLayout(vp: HTMLElement) {
	Object.defineProperty(vp, "clientHeight", { configurable: true, get: () => 100 });
	Object.defineProperty(vp, "scrollHeight", { configurable: true, get: () => box.height });
	Object.defineProperty(vp, "scrollTop", {
		configurable: true,
		get: () => box.top,
		set: (v: number) => {
			box.top = Math.max(0, Math.min(v, box.height - 100));
		},
	});
}

/** The user scrolls the body to `top`. */
function userScroll(top: number) {
	act(() => {
		box.top = top;
		viewport().dispatchEvent(new Event("scroll"));
	});
}

let host: HTMLDivElement;
let root: Root;
const VIEWER = ["viewer"];
const PATH = panePath(VIEWER, "p1");

function land(payload: Record<string, unknown>) {
	act(() => {
		tree.getState().write(PATH.map((s) => [s, null]));
		const props = { ...(tree.getState().getIn(PATH)?.props ?? {}) };
		applyPaneWrite(props, payload);
		tree.getState().setProps(PATH, props);
	});
}

const HEAD = {
	op: "set_head",
	title: "P",
	icon: "",
	key: "",
	system: false,
	editable: false,
	width: "page",
};

function draw() {
	act(() => {
		root.render(
			<TooltipProvider>
				<Pane viewerPath={VIEWER} planeId="p1" cellSpecs={[]} focused />
			</TooltipProvider>,
		);
	});
}

/** A pane with its plane drawn, the viewport's layout faked before any effect reads it. */
function mount(...writes: Record<string, unknown>[]) {
	land(HEAD);
	land({ op: "set_cells", cells: [] });
	draw();
	fakeLayout(viewport());
	for (const w of writes) land(w);
}

beforeEach(() => {
	box.height = 100;
	box.top = 0;
	observers.length = 0;
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
	tree.getState().remove(VIEWER);
});

describe("follow", () => {
	it("pins the body to its end as it grows", () => {
		mount({ op: "set_follow", follow: "bottom" });
		grow(300);
		expect(box.top).toBe(200);
		grow(500);
		expect(box.top).toBe(400);
	});

	it("pauses when the user scrolls up, and resumes at the end", () => {
		mount({ op: "set_follow", follow: "bottom" });
		grow(300);
		userScroll(120);
		grow(500);
		expect(box.top).toBe(120);
		userScroll(400);
		grow(700);
		expect(box.top).toBe(600);
	});

	it("does nothing while none, and stops when turned off", () => {
		mount();
		grow(300);
		expect(box.top).toBe(0);
		land({ op: "set_follow", follow: "bottom" });
		grow(400);
		expect(box.top).toBe(300);
		land({ op: "set_follow", follow: "none" });
		grow(600);
		expect(box.top).toBe(300);
	});
});

describe("a one shot scroll", () => {
	it("applies once per seq: the same command again moves nothing", () => {
		box.height = 500;
		mount({ op: "scroll", to: "bottom", cell_id: "", smooth: false, seq: "s1" });
		expect(box.top).toBe(400);
		userScroll(50);
		land({ op: "scroll", to: "bottom", cell_id: "", smooth: false, seq: "s1" });
		expect(box.top).toBe(50);
		land({ op: "scroll", to: "top", cell_id: "", smooth: false, seq: "s2" });
		expect(box.top).toBe(0);
		userScroll(70);
		land({ op: "scroll", to: "top", cell_id: "", smooth: false, seq: "s3" });
		expect(box.top).toBe(0);
	});

	it("does not replay on a remount", () => {
		box.height = 500;
		mount({ op: "scroll", to: "bottom", cell_id: "", smooth: false, seq: "s1" });
		expect(box.top).toBe(400);
		userScroll(10);
		act(() => root.unmount());
		root = createRoot(host);
		draw();
		fakeLayout(viewport());
		expect(box.top).toBe(10);
	});

	it("drops a malformed command", () => {
		expect(coerceScroll({ to: "middle", seq: "s" })).toBeNull();
		expect(coerceScroll({ to: "top" })).toBeNull();
		expect(coerceScroll({ to: "cell", seq: "s" })).toBeNull();
		expect(coerceScroll({ to: "cell", cell_id: "c1", seq: 3, smooth: true })).toEqual({
			to: "cell",
			cellId: "c1",
			smooth: true,
			seq: "3",
		});
	});

	it("scrolls the viewport to a cell, and waits for one not drawn yet", () => {
		const vp = document.createElement("div");
		fakeLayout(vp);
		box.height = 1000;
		const cmd = { to: "cell" as const, cellId: "c2", smooth: false, seq: "s" };
		expect(applyScroll(vp, cmd)).toBe(false);
		const cell = document.createElement("div");
		cell.dataset.cell = "c2";
		vp.append(cell);
		cell.getBoundingClientRect = () => ({ top: 340 }) as DOMRect;
		vp.getBoundingClientRect = () => ({ top: 40 }) as DOMRect;
		expect(applyScroll(vp, cmd)).toBe(true);
		expect(box.top).toBe(300);
	});
});
