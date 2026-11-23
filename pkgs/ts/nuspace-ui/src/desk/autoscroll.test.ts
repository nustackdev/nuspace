// The edge speed of the drag scroll: nothing in the middle, faster toward an edge.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { dragScroll, EDGE, edgeSpeed, STEP } from "./autoscroll";

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

describe("drag scroll", () => {
	const was = document.elementFromPoint;
	let box: HTMLElement;

	beforeEach(() => {
		vi.useFakeTimers({ toFake: ["requestAnimationFrame", "cancelAnimationFrame", "performance"] });
		// A body 200 tall, scrolling 1000.
		box = document.createElement("div");
		box.style.overflowY = "auto";
		Object.defineProperty(box, "scrollHeight", { value: 1000 });
		Object.defineProperty(box, "clientHeight", { value: 200 });
		box.getBoundingClientRect = () =>
			({ left: 0, top: 0, right: 400, bottom: 200, width: 400, height: 200 }) as DOMRect;
		box.scrollTop = 400;
		document.body.append(box);
		document.elementFromPoint = () => box;
	});
	afterEach(() => {
		box.remove();
		document.elementFromPoint = was;
		vi.useRealTimers();
	});

	it("scrolls down near the bottom and up near the top, each frame", () => {
		const scroll = dragScroll();
		scroll.to(10, 200);
		vi.advanceTimersToNextFrame();
		expect(box.scrollTop).toBe(400 + STEP);
		vi.advanceTimersToNextFrame();
		expect(box.scrollTop).toBe(400 + 2 * STEP);
		scroll.to(10, 0);
		vi.advanceTimersToNextFrame();
		expect(box.scrollTop).toBe(400 + STEP);
		scroll.stop();
	});

	it("goes slower further from the edge, and not at all in the middle", () => {
		const scroll = dragScroll();
		scroll.to(10, 200 - EDGE / 2);
		vi.advanceTimersToNextFrame();
		expect(box.scrollTop).toBe(400 + STEP / 2);
		scroll.to(10, 100);
		vi.advanceTimersToNextFrame();
		expect(box.scrollTop).toBe(400 + STEP / 2);
		scroll.stop();
	});

	it("stops when stopped, and by itself once quiet", () => {
		const scroll = dragScroll();
		scroll.to(10, 200);
		vi.advanceTimersToNextFrame();
		scroll.stop();
		vi.advanceTimersByTime(100);
		expect(box.scrollTop).toBe(400 + STEP);

		const quiet = dragScroll(50);
		quiet.to(10, 200);
		vi.advanceTimersByTime(200);
		const after = box.scrollTop;
		vi.advanceTimersByTime(200);
		expect(box.scrollTop).toBe(after);
		expect(after).toBeGreaterThan(400 + STEP);
	});
});
