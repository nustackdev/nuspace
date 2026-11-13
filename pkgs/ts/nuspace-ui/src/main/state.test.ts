// The viewer's `set_absent` landing in the node's props: it stands in for the
// plane, and a `set_plane` replaces it. `set_trail` keeps beside both. How an absent pane draws is
// ../pane/Absent.test.tsx.

import { OPS } from "@nustackdev/ui-core";
import { nodeAt, tree } from "@nustackdev/ui-kit";
import { describe, expect, it } from "vitest";
import { cellUiPath } from "../plane/cell/address";
import { admits, applyViewerWrite, pruneViewer } from "./state";

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

describe("set_trail", () => {
	const trail = (id: string, crumbs: unknown) => ({ op: "set_trail", plane_id: id, trail: crumbs });

	it("keeps each open pane's trail apart from its plane, whichever lands first", () => {
		const props: Record<string, unknown> = {};
		applyViewerWrite(props, trail("p", [{ id: "a", title: "A" }, { title: "no id" }]), ["p"]);
		applyViewerWrite(props, { op: "set_plane", plane_id: "p", title: "P", meta: {}, cells: [] }, [
			"p",
		]);
		expect(props.trails).toEqual({ p: [{ id: "a", title: "A" }] });
	});

	it("drops a closed pane's trail, and one for a pane no longer open", () => {
		const props: Record<string, unknown> = {};
		applyViewerWrite(props, trail("p", [{ id: "a", title: "A" }]), ["p", "q"]);
		applyViewerWrite(props, trail("q", []), ["q"]);
		applyViewerWrite(props, trail("r", []), ["q"]);
		expect(props.trails).toEqual({ q: [] });
	});
});

// A closed plane's cell ui: taken down when its pane closes, a late frame from
// its run refused, and nothing of it there when the pane opens again.
describe("a closed plane's cell ui", () => {
	const viewer = ["closed-ui", "viewer"];
	const cell = { id: "c1", name: "", source: "", spec: "", draws: true, classes: [] };
	const ui = [...cellUiPath(viewer, "c1"), "out"];
	const draw = (value: string) => ({ op: OPS.write, ref: ui, payload: { value } });

	it("goes on close, stays gone through late frames, and the reopen starts empty", () => {
		tree.getState().write(viewer.map((s) => [s, null]));
		tree.getState().setProps(viewer, {
			planes: { a: { plane_id: "a", title: "A", meta: {}, cells: [cell] } },
		});
		tree.getState().dispatch(draw("old"));
		expect(nodeAt(ui)?.props.value).toBe("old");

		pruneViewer(viewer, ["b"]);
		expect(nodeAt(ui)).toBeNull();
		expect(admits(draw("late"))).toBe(false);
		expect(
			admits({ op: OPS.write, ref: [...cellUiPath(viewer, "c2"), "out"], payload: null }),
		).toBe(true);

		pruneViewer(viewer, ["a"]);
		expect(nodeAt(ui)).toBeNull();
		expect(admits(draw("fresh"))).toBe(true);
	});
});
