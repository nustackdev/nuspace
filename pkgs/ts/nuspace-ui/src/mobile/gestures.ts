// The two touch gestures the mobile shell reads itself: long-press (the
// phone's right-click) and the swipe that closes the sidebar. The kit has no
// gesture helpers yet; these are candidates for it once a second app wants
// them.
//
// Both on pointer events, so a mouse in devtools works the same as a finger.
// The decisions are pure (`swipeCloses`, `pressMoved`) and tested; the hooks
// only feed them.

import type * as React from "react";
import { type RefObject, useEffect, useRef } from "react";

// -- Long-press -----------------------------------------------------------------

/** How long a press holds before it counts as a long-press. iOS and Android sit near here. */
export const LONG_PRESS_MS = 500;

/** How far a finger may drift before the press is a scroll, not a hold. */
export const PRESS_SLOP_PX = 10;

/** Whether a press that started at `from` and is now at `to` has moved off. */
export function pressMoved(
	from: { x: number; y: number },
	to: { x: number; y: number },
	slop = PRESS_SLOP_PX,
): boolean {
	return Math.hypot(to.x - from.x, to.y - from.y) > slop;
}

export type LongPressHandlers = Pick<
	React.HTMLAttributes<HTMLElement>,
	| "onPointerDown"
	| "onPointerMove"
	| "onPointerUp"
	| "onPointerCancel"
	| "onPointerLeave"
	| "onContextMenu"
	| "onClickCapture"
>;

/**
 * Long-press on an element: `onLongPress` after `LONG_PRESS_MS` held still.
 * The tap that ends a long-press is swallowed, so a row that is also a link
 * does not follow it. The browser's own long-press menu (Android's
 * `contextmenu`) is taken over: it fires `onLongPress` too, once.
 */
export function useLongPress(onLongPress: () => void): LongPressHandlers {
	const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
	const start = useRef<{ x: number; y: number } | null>(null);
	const fired = useRef(false);
	const latest = useRef(onLongPress);
	latest.current = onLongPress;

	const stop = () => {
		if (timer.current) clearTimeout(timer.current);
		timer.current = null;
		start.current = null;
	};
	const fire = () => {
		stop();
		if (fired.current) return;
		fired.current = true;
		navigator.vibrate?.(8);
		latest.current();
	};

	useEffect(
		() => () => {
			if (timer.current) clearTimeout(timer.current);
		},
		[],
	);

	return {
		onPointerDown: (e) => {
			if (e.button !== 0) return;
			stop();
			fired.current = false;
			start.current = { x: e.clientX, y: e.clientY };
			timer.current = setTimeout(fire, LONG_PRESS_MS);
		},
		onPointerMove: (e) => {
			if (start.current && pressMoved(start.current, { x: e.clientX, y: e.clientY })) stop();
		},
		onPointerUp: stop,
		onPointerCancel: stop,
		onPointerLeave: stop,
		onContextMenu: (e) => {
			e.preventDefault();
			if (start.current || !fired.current) fire();
		},
		onClickCapture: (e) => {
			if (!fired.current) return;
			fired.current = false;
			e.preventDefault();
			e.stopPropagation();
		},
	};
}

// -- Swipe to close ---------------------------------------------------------------

/** How far left (a share of the panel's width) a released drag must have gone to close. */
export const SWIPE_SHARE = 0.3;

/** How fast (px per ms, leftward) a flick closes whatever the distance. */
export const SWIPE_FLICK = 0.5;

/**
 * Whether a released leftward drag closes the panel: far enough, or a flick
 * fast enough, and still heading left. `dx` is negative for left.
 */
export function swipeCloses(dx: number, velocity: number, width: number): boolean {
	if (dx >= 0) return false;
	return -dx > width * SWIPE_SHARE || -velocity > SWIPE_FLICK;
}

/** Whether a drag of `dx`, `dy` so far is a sideways one, decided once past the slop. */
export function dragAxis(dx: number, dy: number, slop = PRESS_SLOP_PX): "x" | "y" | null {
	if (Math.abs(dx) < slop && Math.abs(dy) < slop) return null;
	return Math.abs(dx) > Math.abs(dy) ? "x" : "y";
}

/**
 * Swipe `ref`'s element left to close it: it follows the finger leftward,
 * and on release either closes (`onClose`) or springs back. A vertical drag
 * is the scroller's, never this. The element wants `touch-action: pan-y`, so
 * the browser leaves the sideways moves to it.
 */
export function useSwipeClose(
	ref: RefObject<HTMLElement | null>,
	enabled: boolean,
	onClose: () => void,
): void {
	const latest = useRef(onClose);
	latest.current = onClose;

	useEffect(() => {
		const el = ref.current;
		if (!el || !enabled) return;
		let from: { x: number; y: number; t: number; id: number } | null = null;
		let axis: "x" | "y" | null = null;
		let last = { x: 0, t: 0, v: 0 };
		let swallow = false;

		const reset = () => {
			el.style.transform = "";
			el.style.transition = "";
			from = null;
			axis = null;
		};
		const down = (e: PointerEvent) => {
			if (e.button !== 0 || from) return;
			swallow = false;
			from = { x: e.clientX, y: e.clientY, t: e.timeStamp, id: e.pointerId };
			last = { x: e.clientX, t: e.timeStamp, v: 0 };
			axis = null;
		};
		const move = (e: PointerEvent) => {
			if (!from || e.pointerId !== from.id) return;
			const dx = e.clientX - from.x;
			axis ??= dragAxis(dx, e.clientY - from.y);
			if (axis !== "x") return;
			const dt = e.timeStamp - last.t;
			if (dt > 0) last = { x: e.clientX, t: e.timeStamp, v: (e.clientX - last.x) / dt };
			el.style.transition = "none";
			el.style.transform = `translateX(${Math.min(0, dx)}px)`;
		};
		const up = (e: PointerEvent) => {
			if (!from || e.pointerId !== from.id) return;
			const dx = e.clientX - from.x;
			const closes = axis === "x" && swipeCloses(dx, last.v, el.offsetWidth);
			reset();
			if (closes) latest.current();
		};
		const cancel = (e: PointerEvent) => {
			if (from && e.pointerId === from.id) reset();
		};
		// A sideways drag that started on a link is no tap.
		const click = (e: MouseEvent) => {
			if (!swallow) return;
			swallow = false;
			e.preventDefault();
			e.stopPropagation();
		};
		const upCapture = () => {
			swallow = axis === "x";
		};
		el.addEventListener("pointerdown", down);
		el.addEventListener("pointermove", move);
		el.addEventListener("pointerup", upCapture, true);
		el.addEventListener("pointerup", up);
		el.addEventListener("pointercancel", cancel);
		el.addEventListener("click", click, true);
		return () => {
			reset();
			el.removeEventListener("pointerdown", down);
			el.removeEventListener("pointermove", move);
			el.removeEventListener("pointerup", upCapture, true);
			el.removeEventListener("pointerup", up);
			el.removeEventListener("pointercancel", cancel);
			el.removeEventListener("click", click, true);
		};
	}, [ref, enabled]);
}
