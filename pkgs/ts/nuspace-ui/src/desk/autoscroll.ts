// Scroll while dragging: a drag held near the edge of something that
// scrolls scrolls it, so a drop can reach what is off screen. The sidebar
// up and down, a strip sideways, a pane's body up and down: anything
// scrollable under the pointer, on either axis.
//
// One listener on the window for every drag, ours or not. The nearest
// scrollable ancestor on each axis under the pointer that can still move
// that way takes the scroll, faster the closer to its edge. It runs each
// frame while drag events keep coming, so holding still near an edge keeps
// scrolling, and stops on drop, on drag end, or when they stop coming.

import { useEffect } from "react";

/** How far in from an edge the scroll starts, px. */
export const EDGE = 40;

/** The most it scrolls per frame, px, right at the edge. */
export const STEP = 16;

/** How long after the last drag event it keeps going, ms. */
const QUIET = 150;

/** The scroll for `pos` between `start` and `end`: negative near the start, positive near the end, else 0. */
export function edgeSpeed(pos: number, start: number, end: number): number {
	const edge = Math.min(EDGE, (end - start) / 3);
	if (pos < start + edge) return -STEP * Math.min(1, (start + edge - pos) / edge);
	if (pos > end - edge) return STEP * Math.min(1, (pos - (end - edge)) / edge);
	return 0;
}

const SCROLLS = /(auto|scroll)/;

/** Scroll the nearest element under (x, y) that can still scroll each way it is near an edge of. */
function nudge(x: number, y: number): void {
	let el = document.elementFromPoint(x, y);
	let doneX = false;
	let doneY = false;
	while (el && !(doneX && doneY)) {
		const style = getComputedStyle(el);
		const r = el.getBoundingClientRect();
		if (!doneX && SCROLLS.test(style.overflowX) && el.scrollWidth > el.clientWidth) {
			const v = edgeSpeed(x, r.left, r.right);
			const was = el.scrollLeft;
			if (v) el.scrollLeft = was + v;
			doneX = el.scrollLeft !== was;
		}
		if (!doneY && SCROLLS.test(style.overflowY) && el.scrollHeight > el.clientHeight) {
			const v = edgeSpeed(y, r.top, r.bottom);
			const was = el.scrollTop;
			if (v) el.scrollTop = was + v;
			doneY = el.scrollTop !== was;
		}
		el = el.parentElement;
	}
}

/** Mount once, at the shell: scroll what is under a drag near its edges. */
export function useDragScroll(): void {
	useEffect(() => {
		let at: { x: number; y: number; t: number } | null = null;
		let frame = 0;
		const tick = () => {
			frame = 0;
			if (!at || performance.now() - at.t > QUIET) {
				at = null;
				return;
			}
			nudge(at.x, at.y);
			frame = requestAnimationFrame(tick);
		};
		const over = (e: DragEvent) => {
			at = { x: e.clientX, y: e.clientY, t: performance.now() };
			if (!frame) frame = requestAnimationFrame(tick);
		};
		const stop = () => {
			at = null;
			cancelAnimationFrame(frame);
			frame = 0;
		};
		window.addEventListener("dragover", over, true);
		window.addEventListener("drop", stop, true);
		window.addEventListener("dragend", stop, true);
		return () => {
			stop();
			window.removeEventListener("dragover", over, true);
			window.removeEventListener("drop", stop, true);
			window.removeEventListener("dragend", stop, true);
		};
	}, []);
}
