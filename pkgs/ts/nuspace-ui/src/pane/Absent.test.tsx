// A pane with no Plane to draw, rendered in jsdom: the viewer's `set_absent`
// landing in the node's props, the empty state per reason, and its close.

import { TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { currentRoutes } from "../core/router";
import { applyViewerWrite } from "../main/state";
import type { AbsentReason } from "../plane/types";
import { ABSENT_TEXT, Pane } from "./Pane";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: Root;

function at(path: string) {
	window.history.replaceState({}, "", path);
}

function render(planeId: string, absent: AbsentReason) {
	act(() => {
		root.render(
			<TooltipProvider>
				<Pane
					viewerPath={["viewer"]}
					planeId={planeId}
					plane={null}
					absent={absent}
					snippets={[]}
					notify={() => {}}
					onMeta={() => {}}
					onRename={() => {}}
					onIcon={() => {}}
					split={false}
					divided={false}
					focused
					style={{}}
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

	it("closes through the pane's close", () => {
		at("/a+gone");
		render("gone", "missing");
		act(() => closeButton()?.click());
		expect(currentRoutes()).toEqual(["a"]);
	});
});

describe("set_absent", () => {
	const plane = { op: "set_plane", plane_id: "p", title: "P", meta: {}, cells: [] };

	it("stands in for the plane, and a set_plane replaces it", () => {
		const props: Record<string, unknown> = {};
		applyViewerWrite(props, plane, ["p"]);
		applyViewerWrite(props, { op: "set_absent", plane_id: "p", reason: "missing" }, ["p"]);
		expect(props.absent).toEqual({ p: "missing" });
		expect(props.planes).toEqual({});
		applyViewerWrite(props, plane, ["p"]);
		expect(props.absent).toEqual({});
		expect(Object.keys(props.planes as object)).toEqual(["p"]);
	});

	it("drops an unknown reason and a pane no longer open", () => {
		const props: Record<string, unknown> = {};
		applyViewerWrite(props, { op: "set_absent", plane_id: "p", reason: "odd" }, ["p"]);
		applyViewerWrite(props, { op: "set_absent", plane_id: "q", reason: "headless" }, ["p"]);
		expect(props.absent ?? {}).toEqual({});
	});
});
