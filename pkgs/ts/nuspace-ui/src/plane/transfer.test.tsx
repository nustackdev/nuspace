// Moving a cell to another plane: the cell menu's "Move to plane" asks for
// the list as it opens, loads until `set_targets` answers on the pane, lists
// every other plane by title, and a pick sends one `cell.transfer`. The
// cell's leaving is the server's.

import { tree } from "@nustackdev/ui-kit";
import { act } from "react";
import { describe, expect, it } from "vitest";
import { applyPaneWrite } from "../pane/state";
import { cell, host, notify, PANE, press, render, selected, typeInto } from "./plane.testing";
import { coerceTargets, type Target, targetsFrom } from "./transfer";

const T = (id: string, title = id.toUpperCase(), icon = ""): Target => ({ id, title, icon });

describe("targetsFrom", () => {
	it("is every other target, by title, untitled ones named so", () => {
		const all = [T("p1"), T("z", "Zed"), T("a", ""), T("b", "Beta")];
		expect(targetsFrom(all, "p1")).toEqual([T("b", "Beta"), T("a", "Untitled"), T("z", "Zed")]);
	});

	it("is nothing when the plane is the only target", () => {
		expect(targetsFrom([T("p1")], "p1")).toEqual([]);
	});
});

describe("the pane's set_targets", () => {
	it("keeps the planes, dropping entries with no id", () => {
		const props: Record<string, unknown> = {};
		applyPaneWrite(props, {
			op: "set_targets",
			planes: [{ id: "p2", title: "Two", icon: "lucide:book" }, { title: "none" }, "junk"],
		});
		expect(props.targets).toEqual([T("p2", "Two", "lucide:book")]);
	});

	it("reads a malformed list as none", () => {
		expect(coerceTargets(null)).toEqual([]);
		expect(coerceTargets({ id: "p2" })).toEqual([]);
	});
});

/** The server's answer to `cell.targets`, landing on the pane's node as its write handler puts it. */
function answer(list: Target[]) {
	act(() => {
		const props: Record<string, unknown> = {};
		applyPaneWrite(props, { op: "set_targets", planes: list });
		tree.getState().setProps(PANE, props);
	});
}

const grip = (id: string) =>
	host.querySelector<HTMLElement>(`[data-cell="${id}"] [data-cell-grip]`) as HTMLElement;
const menuItem = (label: string) =>
	[...document.querySelectorAll<HTMLElement>('[role^="menuitem"]')].find(
		(i) => i.textContent?.trim() === label,
	);
const rows = () => [...document.querySelectorAll<HTMLElement>('[cmdk-item=""]')];
/** The rows' plane ids, in order: cmdk's value on each. */
const ids = () => rows().map((r) => r.getAttribute("data-value"));
const loading = () => document.querySelector('[role="status"][aria-label="Loading planes"]');
const MOVE = "Move to plane…";

function openPicker(id: string) {
	press(grip(id), "Enter");
	act(() => menuItem(MOVE)?.click());
}

describe("Move to plane", () => {
	it("asks as it opens, loads, lists the answer, and sends one transfer to the plane picked", () => {
		render([cell("c1"), cell("c2")]);
		openPicker("c2");
		expect(notify.mock.calls).toEqual([["cell.targets", {}]]);
		expect(loading()).not.toBeNull();
		expect(rows()).toEqual([]);
		answer([T("p1", "Here"), T("p3", "Three"), T("p2", "Two")]);
		expect(loading()).toBeNull();
		expect(ids()).toEqual(["p3", "p2"]);
		expect(rows()[0].textContent).toContain("Three");
		act(() => rows()[1].click());
		expect(notify.mock.calls.at(-1)).toEqual(["cell.transfer", { cell_id: "c2", plane_id: "p2" }]);
		expect(rows()).toEqual([]);
	});

	it("asks afresh each time it opens, loading again until answered", () => {
		render([cell("c1")]);
		openPicker("c1");
		answer([T("p1"), T("p2")]);
		press(document.querySelector("[cmdk-input]") as HTMLElement, "Escape");
		openPicker("c1");
		expect(notify.mock.calls.filter(([op]) => op === "cell.targets")).toHaveLength(2);
		expect(loading()).not.toBeNull();
		answer([T("p1"), T("p4", "Four")]);
		expect(ids()).toEqual(["p4"]);
	});

	it("filters by what is typed", () => {
		render([cell("c1")]);
		openPicker("c1");
		answer([T("p1"), T("p2", "Notes"), T("p3", "Jobs")]);
		typeInto(document.querySelector("[cmdk-input]") as HTMLInputElement, "job");
		expect(ids()).toEqual(["p3"]);
	});

	it("says so when there is nowhere to go", () => {
		render([cell("c1")]);
		openPicker("c1");
		answer([T("p1")]);
		expect(document.body.textContent).toContain("No other plane to move to");
	});

	it("dismissed, sends no transfer and leaves the cell selected", () => {
		render([cell("c1")]);
		openPicker("c1");
		answer([T("p1"), T("p2")]);
		press(document.querySelector("[cmdk-input]") as HTMLElement, "Escape");
		expect(rows()).toEqual([]);
		expect(notify.mock.calls.map(([op]) => op)).toEqual(["cell.targets"]);
		expect(selected()).toEqual(["c1"]);
	});

	it("is not offered on a read-only plane", () => {
		render([cell("c1")], { editable: false });
		press(grip("c1"), "Enter");
		expect(menuItem("Restart cell")).toBeDefined();
		expect(menuItem(MOVE)).toBeUndefined();
	});
});
