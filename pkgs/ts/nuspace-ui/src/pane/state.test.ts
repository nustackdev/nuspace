// A pane node's writes: each of the five state writes lands beside the others, in any
// order, and none needs a plane id. How an absent pane draws is ./Absent.test.tsx.

import { describe, expect, it } from "vitest";
import { LOCAL } from "../core/local";
import { type PlaneInfo, runState } from "../plane/info";
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

	it("keeps follow, and a scroll command until a new seq replaces it", () => {
		const props: Record<string, unknown> = {};
		applyPaneWrite(props, { op: "set_follow", follow: "bottom" });
		expect(props.follow).toBe("bottom");
		applyPaneWrite(props, { op: "set_follow", follow: "odd" });
		expect(props.follow).toBe("none");
		applyPaneWrite(props, { op: "scroll", to: "top", cell_id: "", smooth: false, seq: "s1" });
		const first = props.scroll;
		expect(first).toEqual({ to: "top", cellId: "", smooth: false, seq: "s1" });
		applyPaneWrite(props, { op: "scroll", to: "bottom", cell_id: "", smooth: false, seq: "s1" });
		expect(props.scroll).toBe(first);
		applyPaneWrite(props, { op: "scroll", to: "cell", cell_id: "c1", smooth: true, seq: "s2" });
		expect(props.scroll).toEqual({ to: "cell", cellId: "c1", smooth: true, seq: "s2" });
	});

	it("keeps a cell info answer, times in ms and no run as an empty id", () => {
		const props: Record<string, unknown> = {};
		applyPaneWrite(props, {
			op: "set_cell_info",
			info: {
				cell_id: "c1",
				key: "intro",
				spec: "testing.text",
				label: "Text",
				version: 3,
				created_at: 10,
				modified_at: 0,
				run: { id: "", version: 0 },
			},
		});
		expect(props.cellInfo).toMatchObject({
			cellId: "c1",
			key: "intro",
			label: "Text",
			version: 3,
			createdAt: 10_000,
			modifiedAt: null,
			run: { id: "", startedAt: null },
		});
		applyPaneWrite(props, { op: "set_cell_info", info: { name: "no id" } });
		expect(props.cellInfo).toBeNull();
	});

	it("keeps a plane info answer, its run read as a state like a cell's", () => {
		const props: Record<string, unknown> = {};
		const run = (r: Record<string, unknown>) => {
			applyPaneWrite(props, {
				op: "set_plane_info",
				info: { plane_id: "p1", label: "Jobs", cells: 3, children: 1, run: r },
			});
			const info = props.planeInfo as PlaneInfo;
			return runState(info.run);
		};
		expect(run({ id: "" })).toBe("idle");
		expect(props.planeInfo).toMatchObject({ planeId: "p1", label: "Jobs", cells: 3, children: 1 });
		expect(run({ id: "r", created_at: 1 })).toBe("starting");
		expect(run({ id: "r", started_at: 2 })).toBe("running");
		expect(run({ id: "r", started_at: 2, ended_at: 3, exit: "failed" })).toBe("failed");
		expect(run({ id: "r", started_at: 2, ended_at: 3, exit: "killed" })).toBe("stopped");
		expect(run({ id: "r", started_at: 2, ended_at: 3, exit: "ok" })).toBe("idle");
	});
});
