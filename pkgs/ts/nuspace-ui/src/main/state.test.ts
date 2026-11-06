// The viewer's `set_absent` landing in the node's props: it stands in for the
// plane, and a `set_plane` replaces it. How an absent pane draws is
// ../pane/Absent.test.tsx.

import { describe, expect, it } from "vitest";
import { applyViewerWrite } from "./state";

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
