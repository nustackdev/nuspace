// A program cell that draws nothing, rendered in jsdom: one quiet "No view"
// line on an editable plane and a read-only one alike, and an error stands
// in for it. A cell that draws but whose view has
// not arrived waits quietly, then shows a skeleton; one that drew and cleared
// its view shows the chip.

import { OPS } from "@nustackdev/ui-core";
import { TooltipProvider, tree } from "@nustackdev/ui-kit";
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
	draws: boolean | null = false,
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
						key: "",
						source: "",
						draws,
						classes: [],
						status: { cell_id: "c1", state, error },
					}}
					uiPath={["viewer", "cells", "c1"]}
					panePath={["viewer", "panes", "p1"]}
					editable={editable}
					selected={selection.selected ?? false}
					selectedStrong={(selection.selected ?? false) && (selection.multi ?? false)}
					editing={editing}
					focusReq={null}
					dragging={false}
					setEl={noop}
					onPointerIn={noop}
					onSetEditing={noop}
					onDrag={noop}
					onPlus={noop}
					onDelete={noop}
					onRestart={noop}
					onTransfer={noop}
					onAskInfo={noop}
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

describe("the controls", () => {
	const labels = () =>
		[...host.querySelectorAll("[data-cell-gutter] button")].map((b) =>
			b.getAttribute("aria-label"),
		);

	it("puts add and the grip left of the cell, nothing right", () => {
		render(true, "running");
		expect(labels()).toEqual(["Add a line below", "Drag to reorder, click for options"]);
		const [left, body] = host.querySelectorAll("[data-cell] > *");
		expect(left.hasAttribute("data-cell-gutter")).toBe(true);
		expect(body.hasAttribute("data-cell-body")).toBe(true);
	});

	it("keeps only the menu on a read-only plane", () => {
		render(false, "running");
		expect(labels()).toEqual(["Cell options"]);
		expect(host.querySelector("[data-cell-grip]")?.classList.contains("cursor-grab")).toBe(false);
	});

	it("marks the one selected cell, not a cell in a wider selection", () => {
		const marked = () => host.querySelector("[data-cell]")?.hasAttribute("data-selected");
		render(true, "idle", "", false, { selected: true });
		expect(marked()).toBe(true);
		render(true, "idle", "", false, { selected: true, multi: true });
		expect(marked()).toBe(false);
	});
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
	])("waits, then shows a skeleton, editable=%s draws=%s", (editable, hasUi) => {
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

	it("shows the chip, not the skeleton, once a drawn view is cleared", () => {
		const out = ["viewer", "cells", "c1", "out"];
		render(true, "running", "", true);
		act(() => tree.getState().dispatch({ op: OPS.write, ref: out, payload: { value: "hi" } }));
		expect(body()).not.toContain("No view");
		act(() => tree.getState().dispatch({ op: OPS.remove, ref: out, payload: null }));
		expect(body()).toBe("No view");
		wait(VIEW_LOADER_DELAY_MS);
		expect(loading()).toBe(false);
		expect(body()).toBe("No view");
	});

	it.each(["idle", "stopped"] as const)("keeps waiting on a %s run", (state) => {
		render(false, state, "", true);
		wait(VIEW_LOADER_DELAY_MS);
		expect(loading()).toBe(true);
		expect(body()).not.toContain("No view");
	});
});
