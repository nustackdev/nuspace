// A program cell that draws nothing, rendered in jsdom: one quiet "No view"
// line on an editable plane and a read-only one alike, and an error stands
// in for it. The gutter's source toggle carries the cell's status. A cell that draws but whose view has
// not arrived waits quietly, then shows a skeleton, until its run is over.

import { TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CellState } from "../types";
import { Cell } from "./Cell";
import { VIEW_LOADER_DELAY_MS } from "./Program";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: Root;

function render(
	editable: boolean,
	state: CellState = "idle",
	error = "",
	has_ui: boolean | null = false,
	selection: { selected?: boolean; multi?: boolean } = {},
	editing = false,
) {
	const noop = () => {};
	act(() => {
		root.render(
			<TooltipProvider>
				<Cell
					cell={{
						id: "c1",
						name: "",
						source: "",
						made_by: "",
						has_ui,
						status: { cell_id: "c1", state, error, started_at: 0 },
					}}
					uiPath={["viewer", "cells", "c1"]}
					editable={editable}
					selected={selection.selected ?? false}
					selectedStrong={(selection.selected ?? false) && (selection.multi ?? false)}
					editing={editing}
					focusReq={null}
					dragging={false}
					dropAbove={false}
					setEl={noop}
					onPointerIn={noop}
					onSetEditing={noop}
					onDrag={noop}
					onPlus={noop}
					onDelete={noop}
					onSelect={noop}
					onFocusConsumed={noop}
					onCommit={noop}
					onExit={noop}
				/>
			</TooltipProvider>,
		);
	});
}

const body = () => host.querySelector("[data-cell-body]")?.textContent ?? "";
const loading = () => host.querySelector("[data-view-loading]") !== null;

beforeEach(() => {
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
	vi.useRealTimers();
});

describe("a cell with no view", () => {
	it.each([true, false])("shows the chip, editable=%s", (editable) => {
		render(editable);
		expect(body()).toBe("No view");
	});

	it("keeps the gutter beside it on an editable plane", () => {
		render(true, "running");
		expect(body()).toBe("No view");
		expect(host.querySelector("[data-cell] > :not([data-cell-body])")).not.toBeNull();
	});

	it.each([true, false])("gives way to an error, editable=%s", (editable) => {
		render(editable, "failed", "boom");
		expect(body()).toContain("boom");
		expect(body()).not.toContain("No view");
	});
});

describe("the cell's status, on the source toggle", () => {
	const toggle = () => host.querySelector("[data-cell-status]");

	it.each([
		["idle", "text-cell-idle"],
		["starting", "text-cell-starting"],
		["running", "text-cell-running"],
		["stopped", "text-cell-stopped"],
		["failed", "text-cell-failed"],
		["invalid", "text-cell-invalid"],
	] as [CellState, string][])("tints the glyph and names the state, %s", (state, hue) => {
		render(true, state);
		expect(toggle()?.getAttribute("aria-label")).toBe(`Show source · ${state}`);
		expect(toggle()?.querySelector("svg")?.getAttribute("class")).toContain(hue);
	});

	it("tints it on a read-only plane too", () => {
		render(false, "running");
		expect(toggle()?.getAttribute("aria-label")).toBe("Show source · running");
		expect(toggle()?.querySelector("svg")?.getAttribute("class")).toContain("text-cell-running");
	});
});

describe("the controls", () => {
	const labels = () =>
		[...host.querySelectorAll("[data-cell-gutter] button")].map((b) =>
			b.getAttribute("aria-label"),
		);

	it("puts add and the grip left of the cell, the source toggle right", () => {
		render(true, "running");
		expect(labels()).toEqual([
			"Add a line below",
			"Drag to reorder, click for options",
			"Show source · running",
		]);
		// The right gutter comes before the body, so the body is last in the tab order.
		const [left, right, body] = host.querySelectorAll("[data-cell] > *");
		expect(body.hasAttribute("data-cell-body")).toBe(true);
		expect(left.hasAttribute("data-cell-gutter")).toBe(true);
		expect(right.hasAttribute("data-cell-gutter")).toBe(true);
	});

	it("keeps only the menu and the source toggle on a read-only plane", () => {
		render(false, "running");
		expect(labels()).toEqual(["Cell options", "Show source · running"]);
		expect(host.querySelector("[data-cell-grip]")?.classList.contains("cursor-grab")).toBe(false);
	});

	it("marks the one selected cell, not a cell in a wider selection", () => {
		const marked = () => host.querySelector("[data-cell]")?.hasAttribute("data-selected");
		render(true, "idle", "", false, { selected: true });
		expect(marked()).toBe(true);
		render(true, "idle", "", false, { selected: true, multi: true });
		expect(marked()).toBe(false);
	});

	it.each([
		["failed", false, true],
		["invalid", false, true],
		["running", true, true],
		["running", false, false],
		["idle", false, false],
	] as [CellState, boolean, boolean][])(
		"pins the source toggle out, %s editing=%s",
		(state, editing, pinned) => {
			render(true, state, "", false, {}, editing);
			const lane = host.querySelector("[data-cell-status]")?.closest("[data-cell-gutter]");
			expect(lane?.hasAttribute("data-pinned")).toBe(pinned);
		},
	);
});

describe("a cell whose view is on the way", () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	const wait = (ms: number) => act(() => vi.advanceTimersByTime(ms));

	it.each([
		[true, true],
		[false, true],
		[true, null],
		[false, null],
	])("waits, then shows a skeleton, editable=%s has_ui=%s", (editable, hasUi) => {
		render(editable, "running", "", hasUi);
		expect(body()).toBe("");
		expect(loading()).toBe(false);
		wait(VIEW_LOADER_DELAY_MS - 1);
		expect(loading()).toBe(false);
		wait(1);
		expect(loading()).toBe(true);
		expect(body()).not.toContain("No view");
	});

	it("shows the chip at once when the program draws nothing", () => {
		render(true, "running", "", false);
		expect(body()).toBe("No view");
		expect(loading()).toBe(false);
	});

	it.each([true, false])("gives way to an error, editable=%s", (editable) => {
		render(editable, "running", "", true);
		wait(VIEW_LOADER_DELAY_MS);
		render(editable, "failed", "boom", true);
		expect(loading()).toBe(false);
		expect(body()).toContain("boom");
		expect(body()).not.toContain("No view");
	});

	it.each(["idle", "stopped"] as const)("keeps waiting on a %s run", (state) => {
		render(false, state, "", true);
		wait(VIEW_LOADER_DELAY_MS);
		expect(loading()).toBe(true);
		expect(body()).not.toContain("No view");
	});
});
