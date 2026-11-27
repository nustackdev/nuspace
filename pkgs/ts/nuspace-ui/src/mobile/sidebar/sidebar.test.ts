// The sidebar screen's logic: open as a history entry, a desk's rows on the
// phone and the pages they open, what a plane's long-press offers, the add
// sheet's groups.

import { History } from "@nustackdev/ui-kit";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { Desk, Item } from "../../desk/model";
import { columnKey, itemKey } from "../../sidebar/folders";
import type { PlaneTree, TreeRow } from "../../sidebar/types";
import { pagesOf } from "../desk/model";
import { addGroups } from "./AddPlaneSheet";
import { deskPlanes, deskRows, planeActions } from "./model";
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
	const pick = (rows: ReturnType<typeof deskRows>) =>
		rows.map(({ row, depth, pane, page }) => ({ kind: row.kind, depth, pane, page }));

	it("draws desktop's rows a lane in: item, Strip, Column of 2+, panes", () => {
		expect(pick(deskRows("desk0001", desk, new Set()))).toEqual([
			{ kind: "plane", depth: 1, pane: "", page: 0 },
			{ kind: "strip", depth: 1, pane: "logs", page: 0 },
			{ kind: "column", depth: 2, pane: "logs", page: 0 },
			{ kind: "pane", depth: 3, pane: "logs", page: 0 },
			{ kind: "pane", depth: 3, pane: "errors", page: 1 },
			{ kind: "pane", depth: 2, pane: "alerts", page: 2 },
		]);
	});

	it("maps each pane to the page the pager shows it on", () => {
		const pages = pagesOf(strip);
		for (const r of deskRows("desk0001", desk, new Set())) {
			if (r.row.kind === "pane") expect(pages[r.page].plane).toBe(r.row.plane);
		}
	});

	it("folds a strip and a column as desktop does", () => {
		const col = columnKey("desk0001", "item02", 0);
		expect(pick(deskRows("desk0001", desk, new Set([col]))).map((r) => r.kind)).toEqual([
			"plane",
			"strip",
			"column",
			"pane",
		]);
		const folded = new Set([itemKey("desk0001", "item02")]);
		expect(pick(deskRows("desk0001", desk, folded)).map((r) => r.kind)).toEqual(["plane", "strip"]);
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
