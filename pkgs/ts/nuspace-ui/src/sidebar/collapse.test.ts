// Every sidebar toggle goes through ./collapse.ts: the split in a wide
// window, the overlay in a narrow one, and the split is never touched while
// narrow, so a wide window gets back exactly what it had.

import type { ResizablePanelGroupHandle } from "@nustackdev/ui-kit";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	bindSidebar,
	isSidebarOverlay,
	setSidebarCollapsed,
	setSidebarNarrow,
	setSidebarOverlay,
	toggleSidebar,
} from "./collapse";

/** A split whose sidebar folds and unfolds, every call recorded. */
function fakeSplit(collapsed = false) {
	let folded = collapsed;
	const handle = {
		getLayout: vi.fn(() => [20, 80]),
		setLayout: vi.fn(),
		reset: vi.fn(),
		collapse: vi.fn(() => {
			folded = true;
		}),
		expand: vi.fn(() => {
			folded = false;
		}),
		isCollapsed: vi.fn(() => folded),
	} satisfies ResizablePanelGroupHandle;
	return handle;
}

describe("the sidebar toggles", () => {
	let split: ReturnType<typeof fakeSplit>;
	beforeEach(() => {
		split = fakeSplit();
		bindSidebar({ current: split });
	});
	afterEach(() => {
		setSidebarOverlay(false);
		setSidebarNarrow(false);
		bindSidebar(null);
	});

	it("fold and unfold the split in a wide window", () => {
		setSidebarNarrow(false);
		toggleSidebar();
		expect(split.collapse).toHaveBeenCalledOnce();
		toggleSidebar();
		expect(split.expand).toHaveBeenCalledOnce();
		setSidebarCollapsed(true);
		expect(split.collapse).toHaveBeenCalledTimes(2);
	});

	it("open and close the overlay in a narrow window, the split untouched", () => {
		setSidebarNarrow(true);
		const seen: boolean[] = [];
		const record = () => seen.push(isSidebarOverlay());
		toggleSidebar();
		record();
		toggleSidebar();
		record();
		setSidebarCollapsed(false);
		record();
		setSidebarCollapsed(true);
		record();
		expect(seen).toEqual([true, false, true, false]);
		for (const call of [split.collapse, split.expand, split.setLayout, split.reset])
			expect(call).not.toHaveBeenCalled();
	});

	it("has no overlay in a wide window", () => {
		setSidebarNarrow(false);
		setSidebarOverlay(true);
		expect(isSidebarOverlay()).toBe(false);
	});

	it("closes the overlay when the window leaves narrow, and keeps it closed coming back", () => {
		setSidebarNarrow(true);
		setSidebarOverlay(true);
		expect(isSidebarOverlay()).toBe(true);
		setSidebarNarrow(false);
		expect(isSidebarOverlay()).toBe(false);
		setSidebarNarrow(true);
		expect(isSidebarOverlay()).toBe(false);
	});
});
