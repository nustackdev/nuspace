// A closed pane, settled on the route change: its node goes at once, its
// plane's cell ui is taken down, a late frame from its run refused, and
// nothing of it is there when the pane opens again. The pane node's own
// writes are ../pane/state.test.ts.

import { OPS } from "@nustackdev/ui-core";
import { nodeAt, tree } from "@nustackdev/ui-kit";
import { describe, expect, it } from "vitest";
import { panePath } from "../pane/state";
import { cellUiPath } from "../plane/cell/address";
import { admits, settlePanes } from "./state";

describe("a closed pane", () => {
	const viewer = ["closed-ui", "viewer"];
	const cell = { id: "c1", name: "", key: "", source: "", draws: true, classes: [] };
	const ui = [...cellUiPath(viewer, "c1"), "out"];
	const draw = (value: string) => ({ op: OPS.write, ref: ui, payload: { value } });
	const pane = (id: string) => [...panePath(viewer, id)].map((s) => [s, null] as [string, null]);

	it("goes at once, node and cell ui, stays gone through late frames, and reopens empty", () => {
		tree.getState().write(pane("a"), { cells: [cell] });
		tree.getState().write(pane("b"), { cells: [] });
		tree.getState().dispatch(draw("old"));
		expect(nodeAt(ui)?.props.value).toBe("old");

		settlePanes(viewer, ["b"]);
		expect(nodeAt(panePath(viewer, "a"))).toBeNull();
		expect(nodeAt(panePath(viewer, "b"))).not.toBeNull();
		expect(nodeAt(ui)).toBeNull();
		expect(admits(draw("late"))).toBe(false);
		expect(
			admits({ op: OPS.write, ref: [...cellUiPath(viewer, "c2"), "out"], payload: null }),
		).toBe(true);

		settlePanes(viewer, ["a"]);
		expect(nodeAt(ui)).toBeNull();
		expect(admits(draw("fresh"))).toBe(true);
		expect(nodeAt(panePath(viewer, "b"))).toBeNull();
	});
});
