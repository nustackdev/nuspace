// A pane with no Plane to draw, rendered in jsdom: the empty state per reason,
// and its close where the pane has one, and a pane that had its plane leaving
// once it turns missing. The `set_absent` landing in the pane node's props is
// ./state.test.ts.

import { TooltipProvider, tree } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { currentRoute, currentRoutes, setDesks, setRoles } from "../core/router";
import type { PaneAt } from "../desk/drag";
import { type AbsentReason, coerceHead } from "../plane/types";
import { ABSENT_TEXT, Pane } from "./Pane";
import { applyPaneWrite, panePath } from "./state";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
// The body's scroll area sizes itself with a ResizeObserver, which jsdom lacks.
globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;

let host: HTMLDivElement;
let root: Root;

const IN_STRIP: PaneAt = { kind: "strip", desk: "desk0001", item: "strip1" };

/** Land on a strip of `path`'s planes, "/a+b", one column each. */
function at(path: string) {
	const planes = path.slice(1).split("+").filter(Boolean);
	const columns = planes.map((plane) => ({
		panes: [{ share: 1, original: { plane, params: {} } }],
	}));
	setDesks({ desk0001: { name: "", items: [{ id: "strip1", kind: "strip", columns }] } });
	setRoles({ home: "", settings: "", search: "" });
	window.history.replaceState(null, "", "/d/desk0001/strip1");
}

const VIEWER = ["viewer"];

/** One write onto the pane's node, through its own write body. */
function land(planeId: string, payload: Record<string, unknown>) {
	act(() => {
		const path = panePath(VIEWER, planeId);
		tree.getState().write(path.map((s) => [s, null]));
		const props = { ...(tree.getState().getIn(path)?.props ?? {}) };
		applyPaneWrite(props, payload);
		tree.getState().setProps(path, props);
	});
}

function draw(planeId: string, where: PaneAt) {
	act(() => {
		root.render(
			<TooltipProvider>
				<Pane viewerPath={VIEWER} at={where} planeId={planeId} cellSpecs={[]} focused />
			</TooltipProvider>,
		);
	});
}

function render(planeId: string, absent: AbsentReason, where: PaneAt = IN_STRIP) {
	land(planeId, { op: "set_absent", reason: absent });
	draw(planeId, where);
}

const closeButton = () =>
	[...host.querySelectorAll("button")].find((b) => b.textContent === "Close");

beforeEach(() => {
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
	tree.getState().remove(VIEWER);
});

describe("absent pane", () => {
	it("says a missing plane does not exist, titled by its id, nothing to edit", () => {
		render("gone", "missing");
		expect(host.textContent).toContain(ABSENT_TEXT.missing);
		expect(host.textContent).toContain("gone");
		expect(host.textContent).not.toContain("loading");
		expect(host.querySelector("h1")).toBeNull();
		expect(closeButton()).toBeDefined();
	});

	it("says a headless plane runs without a view, with no links", () => {
		render("svc", "headless");
		expect(host.textContent).toContain(ABSENT_TEXT.headless);
		expect(host.querySelector("a")).toBeNull();
		expect(host.querySelector("h1")).toBeNull();
		expect(closeButton()).toBeDefined();
	});

	it("has no close on a solo plane", () => {
		render("gone", "missing", { kind: "solo" });
		expect(host.textContent).toContain(ABSENT_TEXT.missing);
		expect(closeButton()).toBeUndefined();
	});

	it("closes through the pane's close", () => {
		at("/a+gone");
		render("gone", "missing");
		act(() => closeButton()?.click());
		expect(currentRoutes()).toEqual(["a"]);
	});

	it("leaves once its plane goes: a solo pane goes home", () => {
		setDesks({});
		setRoles({ home: "", settings: "", search: "" });
		window.history.replaceState(null, "", "/p/gone");
		land("gone", { op: "set_head", ...coerceHead({}), title: "Gone" });
		draw("gone", { kind: "solo" });
		expect(currentRoute().kind).toBe("solo");
		land("gone", { op: "set_absent", reason: "missing" });
		expect(window.location.pathname).toBe("/");
	});

	it("stays when it never had its plane: a link to nothing says so", () => {
		setDesks({});
		setRoles({ home: "", settings: "", search: "" });
		window.history.replaceState(null, "", "/p/never");
		render("never", "missing", { kind: "solo" });
		expect(window.location.pathname).toBe("/p/never");
		expect(host.textContent).toContain(ABSENT_TEXT.missing);
	});
});
