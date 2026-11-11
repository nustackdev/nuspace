// The edge speed of the drag scroll: nothing in the middle, faster toward an edge.

import { describe, expect, it } from "vitest";
import { EDGE, edgeSpeed, STEP } from "./autoscroll";

describe("edge speed", () => {
	it("is 0 away from the edges", () => {
		expect(edgeSpeed(500, 0, 1000)).toBe(0);
		expect(edgeSpeed(EDGE, 0, 1000)).toBe(0);
	});

	it("scrolls back near the start and on near the end, fastest at the edge", () => {
		expect(edgeSpeed(0, 0, 1000)).toBe(-STEP);
		expect(edgeSpeed(EDGE / 2, 0, 1000)).toBe(-STEP / 2);
		expect(edgeSpeed(1000, 0, 1000)).toBe(STEP);
		expect(edgeSpeed(1000 - EDGE / 2, 0, 1000)).toBe(STEP / 2);
	});

	it("never goes past full speed outside the box", () => {
		expect(edgeSpeed(-50, 0, 1000)).toBe(-STEP);
		expect(edgeSpeed(1200, 0, 1000)).toBe(STEP);
	});
});
