// The touch gestures' decisions: when a press has moved off, which way a drag
// goes, when a released swipe closes the sidebar.

import { describe, expect, it } from "vitest";
import { dragAxis, PRESS_SLOP_PX, pressMoved, swipeCloses } from "./gestures";

describe("pressMoved", () => {
	it("holds within the slop and moves off past it", () => {
		expect(pressMoved({ x: 0, y: 0 }, { x: 6, y: 6 })).toBe(false);
		expect(pressMoved({ x: 0, y: 0 }, { x: PRESS_SLOP_PX + 1, y: 0 })).toBe(true);
	});
});

describe("dragAxis", () => {
	it("waits for the slop, then takes the larger move", () => {
		expect(dragAxis(4, 3)).toBeNull();
		expect(dragAxis(-30, 8)).toBe("x");
		expect(dragAxis(5, -30)).toBe("y");
	});
});

describe("swipeCloses", () => {
	it("closes past a third of the width, or on a flick", () => {
		expect(swipeCloses(-150, 0, 375)).toBe(true);
		expect(swipeCloses(-60, 0, 375)).toBe(false);
		expect(swipeCloses(-60, -0.9, 375)).toBe(true);
	});

	it("never closes on a drag to the right", () => {
		expect(swipeCloses(120, 1, 375)).toBe(false);
		expect(swipeCloses(0, -2, 375)).toBe(false);
	});
});
