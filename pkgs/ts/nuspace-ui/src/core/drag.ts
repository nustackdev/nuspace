// A horizontal drag, from the pointerdown that starts it to the release.
//
// Both resize handles (the sidebar's edge and the borders between panes) are
// the same gesture, so the plumbing is written once: listen on the window so a
// fast pointer that leaves the handle keeps dragging, and hold a col-resize
// cursor and no text selection on the body for as long as it lasts, so the
// pointer does not flicker or paint a selection across whatever it crosses.
// A press that never travels past a few pixels is a click, not a drag: it
// moves nothing and fires `onClick` instead, which both handles use to snap
// back to their default.

import type * as React from "react";

/** How far a press travels before it is a drag rather than a click. */
export const CLICK_SLOP = 3;

/**
 * Track one drag started by `e`. `onMove` gets the distance from the start on
 * every move once the press has travelled past the slop, `onEnd` fires once on
 * release or cancel of a drag, and `onClick` instead when it never travelled.
 * Primary button only: returns false, and tracks nothing, for any other.
 */
export function trackColDrag(
	e: React.PointerEvent,
	onMove: (dx: number) => void,
	onEnd?: () => void,
	onClick?: () => void,
): boolean {
	if (e.button !== 0) return false;
	e.preventDefault();
	const startX = e.clientX;
	const body = document.body.style;
	const prevCursor = body.cursor;
	const prevSelect = body.userSelect;
	body.cursor = "col-resize";
	body.userSelect = "none";
	let dragging = false;
	const move = (ev: PointerEvent) => {
		const dx = ev.clientX - startX;
		if (!dragging && Math.abs(dx) < CLICK_SLOP) return;
		dragging = true;
		onMove(dx);
	};
	const up = (ev: PointerEvent) => {
		window.removeEventListener("pointermove", move);
		window.removeEventListener("pointerup", up);
		window.removeEventListener("pointercancel", up);
		body.cursor = prevCursor;
		body.userSelect = prevSelect;
		if (dragging) onEnd?.();
		else if (ev.type === "pointerup") onClick?.();
	};
	window.addEventListener("pointermove", move);
	window.addEventListener("pointerup", up);
	window.addEventListener("pointercancel", up);
	return true;
}
