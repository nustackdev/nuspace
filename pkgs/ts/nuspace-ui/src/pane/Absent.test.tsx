// A pane with no Plane to draw, rendered in jsdom: the empty state per reason,
// and its close where the pane has one. The viewer's `set_absent` landing in the node's props is
// ../main/state.test.ts.

import { TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { currentRoutes, setDesks, setRoles } from "../core/router";
import type { PaneAt } from "../desk/drag";
import type { AbsentReason } from "../plane/types";
import { ABSENT_TEXT, Pane } from "./Pane";

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

function render(planeId: string, absent: AbsentReason, where: PaneAt = IN_STRIP) {
	act(() => {
		root.render(
			<TooltipProvider>
				<Pane
					viewerPath={["viewer"]}
					at={where}
					planeId={planeId}
					plane={null}
					absent={absent}
					cellSpecs={[]}
					notify={() => {}}
					onMeta={() => {}}
					onRename={() => {}}
					onIcon={() => {}}
					focused
				/>
			</TooltipProvider>,
		);
	});
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
});
