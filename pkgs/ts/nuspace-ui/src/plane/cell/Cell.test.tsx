// A program cell that draws nothing, rendered in jsdom: one quiet "No view"
// line on an editable plane and a read-only one alike, beside the gutter's
// status, and an error stands in for it.

import { TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { CellState } from "../types";
import { Cell } from "./Cell";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: Root;

function render(editable: boolean, state: CellState = "idle", error = "") {
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

beforeEach(() => {
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
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
