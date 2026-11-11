// Share resizing as numbers: the shares after a border moves.

import { describe, expect, it } from "vitest";
import { PANE_MIN, resizeShares } from "./sizes";

describe("pane shares", () => {
	it("moves only the border's two panes, by the px over the room", () => {
		const out = resizeShares([0.5, 0.25, 0.25], 0, 30, 600);
		expect(out[0]).toBeCloseTo(0.55, 9);
		expect(out[1]).toBeCloseTo(0.2, 9);
		expect(out[2]).toBe(0.25);
	});

	it("never takes a pane under the min", () => {
		const out = resizeShares([0.5, 0.5], 0, 10_000, 600);
		expect(out[1]).toBeCloseTo(PANE_MIN / 600, 9);
		expect(out[0] + out[1]).toBeCloseTo(1, 9);
		expect(resizeShares([0.5, 0.5], 0, -10_000, 600)[0]).toBeCloseTo(PANE_MIN / 600, 9);
	});

	it("collapses a pane resized under the collapse height to its header", () => {
		const down = resizeShares([0.5, 0.5], 0, 220, 600);
		expect(down[1]).toBeCloseTo(PANE_MIN / 600, 9);
		const up = resizeShares([0.5, 0.5], 0, -220, 600);
		expect(up[0]).toBeCloseTo(PANE_MIN / 600, 9);
		expect(resizeShares([0.5, 0.5], 0, 190, 600)[1]).toBeCloseTo(110 / 600, 9);
	});

	it("leaves the shares alone with no room or no border", () => {
		expect(resizeShares([0.5, 0.5], 0, 40, 0)).toEqual([0.5, 0.5]);
		expect(resizeShares([0.5, 0.5], 1, 40, 600)).toEqual([0.5, 0.5]);
	});
});
