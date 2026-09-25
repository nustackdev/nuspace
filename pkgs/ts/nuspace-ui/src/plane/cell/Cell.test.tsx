// A program cell that draws nothing, rendered in jsdom: one quiet "No view"
// line on an editable plane and a read-only one alike, beside the gutter's
// status, and an error stands in for it. A cell that draws but whose view has
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
					selected={false}
					selectedStrong={false}
					focused={false}
					editing={false}
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
