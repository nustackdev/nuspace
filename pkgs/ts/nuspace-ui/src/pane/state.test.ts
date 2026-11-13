// A pane node's writes: each of the five lands beside the others, in any
// order, and none needs a plane id. How an absent pane draws is ./Absent.test.tsx.

import { describe, expect, it } from "vitest";
import { LOCAL } from "../core/local";
import { EMPTY_EDITOR } from "../plane/state";
import type { Cell } from "../plane/types";
import { applyPaneWrite, panePath } from "./state";

const HEAD = {
	op: "set_head",
	title: "P",
	icon: "emoji:🌱",
	key: "p-1",
	system: false,
	editable: true,
	width: "board",
};
const cell = (id: string) => ({ id, name: id, key: "", source: "", draws: true, classes: [] });

describe("a pane node", () => {
	it("lives under the viewer, at panes/<plane>", () => {
		expect(panePath(["shell", "viewer"], "p")).toEqual(["shell", "viewer", "panes", "p"]);
	});

	it("takes its head with the flat fields folded into meta", () => {
		const props: Record<string, unknown> = {};
		applyPaneWrite(props, HEAD);
		expect(props.head).toEqual({
			title: "P",
			system: false,
			meta: { editable: true, width: "board", key: "p-1", icon: "emoji:🌱" },
		});
	});

	it("keeps statuses by cell and folds them into cells, whichever lands first", () => {
		const props: Record<string, unknown> = {};
		applyPaneWrite(props, {
			op: "set_status",
			statuses: [{ cell_id: "a", state: "running", error: "" }],
		});
		applyPaneWrite(props, { op: "set_cells", cells: [cell("a"), cell("b")] });
		const states = () => (props.cells as Cell[]).map((c) => c.status.state);
		expect(states()).toEqual(["running", "idle"]);
		applyPaneWrite(props, {
			op: "set_status",
			statuses: [
				{ cell_id: "a", state: "failed", error: "boom" },
				{ cell_id: "b", state: "stopped", error: "" },
			],
		});
		expect(states()).toEqual(["failed", "stopped"]);
		// A head reshipped leaves the cells as they are: a rename is no cell write.
		const cells = props.cells;
		applyPaneWrite(props, { ...HEAD, title: "Q" });
		expect(props.cells).toBe(cells);
	});

	it("prunes its editor state of cells that went", () => {
		const props: Record<string, unknown> = {
			[LOCAL]: { ...EMPTY_EDITOR, selected: ["a", "b"], editing: ["b"] },
		};
		applyPaneWrite(props, { op: "set_cells", cells: [cell("a")] });
		expect(props[LOCAL]).toMatchObject({ selected: ["a"], editing: [] });
	});

	it("keeps its trail apart from the head, either first", () => {
		const props: Record<string, unknown> = {};
		applyPaneWrite(props, { op: "set_trail", trail: [{ id: "a", title: "A" }, { title: "x" }] });
		applyPaneWrite(props, HEAD);
		expect(props.trail).toEqual([{ id: "a", title: "A" }]);
	});

	it("goes absent in place of its head, and a head brings it back", () => {
		const props: Record<string, unknown> = {};
		applyPaneWrite(props, HEAD);
		applyPaneWrite(props, { op: "set_absent", reason: "missing" });
		expect(props.absent).toBe("missing");
		expect(props.head).toBeUndefined();
		applyPaneWrite(props, HEAD);
		expect(props.absent).toBeUndefined();
		expect((props.head as { title: string }).title).toBe("P");
	});

	it("drops an unknown absent reason and an unknown op", () => {
		const props: Record<string, unknown> = {};
		applyPaneWrite(props, { op: "set_absent", reason: "odd" });
		applyPaneWrite(props, { op: "set_plane", title: "old" });
		expect(props).toEqual({});
	});
});
