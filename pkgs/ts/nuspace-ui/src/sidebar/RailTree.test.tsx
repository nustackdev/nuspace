// The rail's icon and chevron slot, rendered in jsdom.
//
// jsdom applies no stylesheet, so the CSS swap itself (icon at rest, chevron on
// hover, one row at a time) is checked in a real browser. What is checked here
// is everything the swap stands on: every row carries both the icon and a real
// chevron button, the button only folds, and an open leaf says so.

import { TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RailTree } from "./RailTree";
import { visibleRows } from "./tree";
import { childrenOf, coerceTree, ROOT_ID } from "./types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// a (with a1), b at the top.
const tree = coerceTree([
	{ id: ROOT_ID, kind: "space", title: "", parent: ROOT_ID, children: ["a", "b"] },
	{ id: "a", kind: "plane", title: "A", parent: ROOT_ID, children: ["a1"] },
	{ id: "a1", kind: "plane", title: "A1", parent: "a", children: [] },
	{ id: "b", kind: "plane", title: "B", parent: ROOT_ID, children: [] },
]);

let host: HTMLDivElement;
let root: Root;
const onToggle = vi.fn();

function render(expanded: string[]) {
	const rows = visibleRows(tree, childrenOf(tree, ROOT_ID), new Set(expanded));
	act(() => {
		root.render(
			<TooltipProvider>
				<RailTree
					tree={tree}
					rows={rows}
					registered={[]}
					routes={[]}
					selKey=""
					onToggle={onToggle}
					reveal={() => {}}
					notify={() => {}}
				/>
			</TooltipProvider>,
		);
	});
}

const rowOf = (key: string) =>
	host.querySelector<HTMLElement>(`[role="treeitem"][data-rail-key="${key}"]`);
const chevronOf = (key: string) => rowOf(key)?.querySelector<HTMLButtonElement>("button");

beforeEach(() => {
	window.history.replaceState({}, "", "/");
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
	onToggle.mockClear();
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

describe("rail icon and chevron slot", () => {
	it("gives every row, leaf or not, its icon and a chevron button", () => {
		render(["a"]);
		for (const key of ["a", "a1", "b"]) {
			const lane = rowOf(key)?.firstElementChild;
			expect(lane?.querySelector(":scope > svg")).not.toBeNull();
			expect(lane?.querySelector(":scope > button")).not.toBeNull();
		}
		expect(chevronOf("a")?.getAttribute("aria-label")).toBe("Collapse");
		expect(chevronOf("a")?.getAttribute("aria-expanded")).toBe("true");
		expect(chevronOf("b")?.getAttribute("aria-label")).toBe("Expand");
		expect(chevronOf("b")?.getAttribute("aria-expanded")).toBe("false");
		expect(rowOf("b")?.getAttribute("aria-expanded")).toBe("false");
	});

	it("stacks a click-through icon over a chevron hidden at rest", () => {
		render([]);
		const lane = rowOf("b")?.firstElementChild;
		// At opacity 0 the icon paints above the chevron, so it must never
		// take the pointer, or it eats the chevron's click.
		expect(lane?.querySelector("svg")?.getAttribute("class")).toContain("pointer-events-none");
		expect(chevronOf("b")?.className).toMatch(/(^| )opacity-0( |$)/);
		expect(chevronOf("b")?.className).toContain("group-hover/row:opacity-100");
	});

	it("folds on a chevron click and never navigates", () => {
		render(["a"]);
		const outer = vi.fn();
		// Above the React root, so it sees what the row would.
		document.body.addEventListener("click", outer);
		act(() => chevronOf("a")?.click());
		document.body.removeEventListener("click", outer);
		expect(onToggle).toHaveBeenCalledWith("a");
		expect(outer).not.toHaveBeenCalled();
		expect(window.location.pathname).toBe("/");
	});

	it("keeps a press on the chevron from focusing it or starting a drag", () => {
		render([]);
		const down = new MouseEvent("mousedown", { bubbles: true, cancelable: true });
		chevronOf("b")?.dispatchEvent(down);
		expect(down.defaultPrevented).toBe(true);
	});

	it("presses the chevron with Enter without opening the plane", () => {
		render([]);
		const enter = new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true });
		act(() => {
			chevronOf("b")?.dispatchEvent(enter);
		});
		// The row's Enter would have prevented the press and opened the plane.
		expect(enter.defaultPrevented).toBe(false);
		expect(window.location.pathname).toBe("/");
	});

	it("unfolds a leaf into one muted line and nothing focusable", () => {
		render([]);
		expect(host.textContent).not.toContain("No planes inside");
		render(["b"]);
		expect(host.textContent).toContain("No planes inside");
		expect(host.querySelectorAll('[role="treeitem"]').length).toBe(2);
		render(["a"]);
		expect(host.textContent).not.toContain("No planes inside");
	});

	it("unfolds a folded leaf with ArrowRight and folds it with ArrowLeft", () => {
		render([]);
		const right = new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true });
		act(() => {
			rowOf("b")?.dispatchEvent(right);
		});
		expect(onToggle).toHaveBeenLastCalledWith("b");
		render(["b"]);
		const left = new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true });
		act(() => {
			rowOf("b")?.dispatchEvent(left);
		});
		expect(onToggle).toHaveBeenCalledTimes(2);
	});
});
