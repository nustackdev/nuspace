// A horizontal drag, from the pointerdown that starts it to the release.
//
// Both resize handles (the sidebar's edge and the borders between panes) are
// the same gesture, so the plumbing is written once: listen on the window so a
// fast pointer that leaves the handle keeps dragging, and hold a col-resize
// cursor and no text selection on the body for as long as it lasts, so the
// pointer does not flicker or paint a selection across whatever it crosses.

import type * as React from "react";

/**
 * Track one drag started by `e`. `onMove` gets the distance from the start on
 * every move, `onEnd` fires once on release or cancel. Primary button only:
 * returns false, and tracks nothing, for any other.
 */
export function trackColDrag(
	e: React.PointerEvent,
	onMove: (dx: number) => void,
	onEnd?: () => void,
): boolean {
	if (e.button !== 0) return false;
	e.preventDefault();
	const startX = e.clientX;
	const body = document.body.style;
	const prevCursor = body.cursor;
	const prevSelect = body.userSelect;
	body.cursor = "col-resize";
	body.userSelect = "none";
	const move = (ev: PointerEvent) => onMove(ev.clientX - startX);
	const up = () => {
		window.removeEventListener("pointermove", move);
		window.removeEventListener("pointerup", up);
		window.removeEventListener("pointercancel", up);
		body.cursor = prevCursor;
		body.userSelect = prevSelect;
		onEnd?.();
	};
	window.addEventListener("pointermove", move);
	window.addEventListener("pointerup", up);
	window.addEventListener("pointercancel", up);
	return true;
}
