// The sidebar screen's logic: open as a history entry, a desk's rows on the
// phone and the pages they open, what a plane's long-press offers, the add
// sheet's groups.

import { History } from "@nustackdev/ui-kit";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { Desk, Item } from "../../desk/model";
import type { PlaneTree, TreeRow } from "../../sidebar/types";
import { pageOf, pagesOf } from "../desk/model";
import { addGroups } from "./AddPlaneSheet";
import { deskPlanes, deskRows, planeActions, stackOf, stripLabel } from "./model";
import {
	isSidebarEntry,
	leaveThen,
	markState,
	openSidebar,
	SIDEBAR_STATE,
	settleSidebar,
} from "./open";

const link = (plane: string) => ({ original: { plane, params: {} } });

describe("deskRows", () => {
	// Two columns: logs over errors, then alerts. Pages in reading order: logs, errors, alerts.
	const desk: Desk = {
		name: "Ops",
		items: [
			{ id: "item01", kind: "plane", ...link("deploys") },
			{
				id: "item02",
				kind: "strip",
				columns: [
					{
						panes: [
							{ share: 1, ...link("logs") },
							{ share: 1, ...link("errors") },
						],
					},
					{ panes: [{ share: 1, ...link("alerts") }] },
				],
			},
		],
	};
	const strip = desk.items[1] as Extract<Item, { kind: "strip" }>;

	it("draws one row per item, a strip as one row", () => {
		expect(deskRows(desk).map((r) => [r.item.id, r.item.kind])).toEqual([
			["item01", "plane"],
			["item02", "strip"],
		]);
	});

	it("names a strip's planes in the pager's order, column by column", () => {
		const [plane, row] = deskRows(desk);
		expect(plane.planes).toEqual(["deploys"]);
		expect(row.planes).toEqual(["logs", "errors", "alerts"]);
		expect(row.planes).toEqual(pagesOf(strip).map((p) => p.plane));
	});

	it("opens a strip on the pager's first page, a plane item as itself", () => {
		const [plane, row] = deskRows(desk);
		expect(plane.pane).toBe("");
		expect(row.pane).toBe("logs");
		expect(pageOf(pagesOf(strip), row.pane)).toBe(0);
	});

	it("stacks up to three icons, then counts the rest", () => {
		expect(stackOf(["a", "b"])).toEqual({ shown: ["a", "b"], more: 0 });
		expect(stackOf(["a", "b", "c"])).toEqual({ shown: ["a", "b", "c"], more: 0 });
		expect(stackOf(["a", "b", "c", "d", "e"])).toEqual({ shown: ["a", "b", "c"], more: 2 });
	});

	it("labels a strip by its count", () => {
		expect(stripLabel(3)).toBe("3 planes");
		expect(stripLabel(1)).toBe("1 plane");
	});

	it("names every plane the rows can show, for their looks", () => {
		expect(deskPlanes([desk])).toEqual(["deploys", "logs", "errors", "alerts"]);
	});
});

const row = (id: string, system = false): TreeRow => ({
	id,
	kind: "plane",
	title: id,
	parent: "space",
	children: [],
	spec: "",
	icon: "",
	system,
});

describe("planeActions", () => {
	const tree: PlaneTree = { mine: row("mine"), sys: row("sys", true) };

	it("offers rename, add inside and delete", () => {
		expect(planeActions(tree, "mine")).toEqual(["rename", "inside", "delete"]);
	});

	it("offers no delete on a system plane", () => {
		expect(planeActions(tree, "sys")).toEqual(["rename", "inside"]);
	});

	it("offers nothing for a plane the tree does not hold", () => {
		expect(planeActions(tree, "gone")).toEqual([]);
	});
});

describe("addGroups", () => {
	it("groups registered planes by package, in first-seen order", () => {
		const r = (name: string) => ({ name, label: name, group: "", icon: "", description: "" });
		const groups = addGroups([r("nuverse.notes"), r("ops.board"), r("nuverse.todo")]);
		expect(groups.map((g) => [g.pkg, g.entries.map((e) => e.name)])).toEqual([
			["nuverse", ["nuverse.notes", "nuverse.todo"]],
			["ops", ["ops.board"]],
		]);
	});
});

describe("the sidebar as a history entry", () => {
	beforeEach(() => {
		window.history.replaceState(null, "", "/p/home");
	});
	afterEach(() => {
		window.history.replaceState(null, "", "/");
	});

	it("marks state without losing what was there", () => {
		expect(markState(null, true)).toEqual({ [SIDEBAR_STATE]: true });
		expect(markState({ a: 1 }, true)).toEqual({ a: 1, [SIDEBAR_STATE]: true });
		expect(markState({ a: 1, [SIDEBAR_STATE]: true }, false)).toEqual({ a: 1 });
		expect(markState({ [SIDEBAR_STATE]: true }, false)).toBeNull();
	});

	it("opens by pushing the same url with the mark", () => {
		const before = window.history.length;
		openSidebar();
		expect(window.history.length).toBe(before + 1);
		expect(History.current().url).toBe("/p/home");
		expect(isSidebarEntry(History.current())).toBe(true);
		// Open already: no second entry.
		openSidebar();
		expect(window.history.length).toBe(before + 1);
	});

	it("leaves by going back first, then moving on", async () => {
		openSidebar();
		const moved = new Promise<string>((resolve) => {
			leaveThen(() => {
				resolve(History.current().url);
				History.push("/p/notes");
			});
		});
		// Back landed on the entry under the sidebar's, before the move.
		expect(await moved).toBe("/p/home");
		expect(isSidebarEntry(History.current())).toBe(false);
		expect(History.current().url).toBe("/p/notes");
	});

	it("moves on at once when closed", () => {
		let ran = false;
		leaveThen(() => {
			ran = true;
		});
		expect(ran).toBe(true);
	});

	it("drops the mark in place after a reload while open", () => {
		window.history.replaceState({ [SIDEBAR_STATE]: true }, "", "/p/home");
		const before = window.history.length;
		settleSidebar();
		expect(isSidebarEntry(History.current())).toBe(false);
		expect(window.history.length).toBe(before);
	});
});
