// A pane body's scroll, driven from the server or a cell. Mirrors the
// `set_follow` and `scroll` writes in `nuspace/web/viewer/interactions.py`.
//
// Two things ride the pane's node (./state.ts):
//
//   follow  state: "bottom" keeps the body at its end as it grows. The user
//           scrolling up pauses it, coming back to the end resumes it. The
//           pause is the browser's alone: nothing goes back to the server
//   scroll  a one shot command {to, cell_id, smooth, seq}. Applied once per
//           new seq: the seq applied last is kept on the node too
//           (`scrolled`), so a remount or the same command landing again
//           moves nothing
//
// Growth is heard with a ResizeObserver on the body's content and on the
// viewport itself (a pane made shorter is growth too). A scroll that moves
// the body down never pauses: only a move up does, so a smooth scroll to the
// end, or the browser clamping the top when content shrinks, keeps following.
//
// The viewport is the kit ScrollArea's, through its `viewportRef`.

import { type RefObject, useEffect, useRef } from "react";

export type Follow = "none" | "bottom";

export type ScrollTo = "top" | "bottom" | "cell";

export interface ScrollCommand {
	to: ScrollTo;
	cellId: string;
	smooth: boolean;
	seq: string;
}

/** Within this many px of the end reads as at the end: subpixel rounding, zoom. */
const AT_END_SLACK = 2;

export function coerceFollow(raw: unknown): Follow {
	return raw === "bottom" ? "bottom" : "none";
}

/** A `scroll` write as a command, null when it is malformed. */
export function coerceScroll(raw: unknown): ScrollCommand | null {
	const p = (raw ?? {}) as Record<string, unknown>;
	const to = p.to;
	if (to !== "top" && to !== "bottom" && to !== "cell") return null;
	const seq = typeof p.seq === "string" || typeof p.seq === "number" ? String(p.seq) : "";
	if (!seq) return null;
	const cellId = typeof p.cell_id === "string" ? p.cell_id : "";
	if (to === "cell" && !cellId) return null;
	return { to, cellId, smooth: p.smooth === true, seq };
}

/** Whether the viewport shows its end. */
export function atEnd(vp: HTMLElement): boolean {
	return vp.scrollHeight - vp.scrollTop - vp.clientHeight <= AT_END_SLACK;
}

function scrollTop(vp: HTMLElement, top: number, smooth: boolean): void {
	if (smooth && typeof vp.scrollTo === "function") vp.scrollTo({ top, behavior: "smooth" });
	else vp.scrollTop = top;
}

/**
 * Apply one command to the viewport. False when it cannot yet: the cell it
 * names is not drawn. Scrolls the viewport alone, never the strip around it.
 */
export function applyScroll(vp: HTMLElement, cmd: ScrollCommand): boolean {
	if (cmd.to === "top") {
		scrollTop(vp, 0, cmd.smooth);
		return true;
	}
	if (cmd.to === "bottom") {
		scrollTop(vp, vp.scrollHeight, cmd.smooth);
		return true;
	}
	// Ids are slugs (key chars), so they sit in a selector as they are.
	const el = vp.querySelector<HTMLElement>(`[data-cell="${cmd.cellId}"]`);
	if (!el) return false;
	const top = el.getBoundingClientRect().top - vp.getBoundingClientRect().top + vp.scrollTop;
	scrollTop(vp, top, cmd.smooth);
	return true;
}

/**
 * Drive the viewport from the pane's node: follow while asked, and each new
 * one shot command once. `ready` is whether the plane is drawn: a command
 * waits for it, and a command to a cell not drawn yet waits for the content
 * to grow it in. `onApplied` keeps the seq on the node.
 */
export function useScroller({
	viewport,
	content,
	follow,
	scroll,
	applied,
	ready,
	onApplied,
}: {
	viewport: RefObject<HTMLElement | null>;
	content: RefObject<HTMLElement | null>;
	follow: Follow;
	scroll: ScrollCommand | null;
	applied: string | null;
	ready: boolean;
	onApplied: (seq: string) => void;
}): void {
	const pinned = useRef(true);

	useEffect(() => {
		const vp = viewport.current;
		const body = content.current;
		if (follow !== "bottom" || !vp || !body) return;
		pinned.current = true;
		vp.scrollTop = vp.scrollHeight;
		let last = vp.scrollTop;
		const onScroll = () => {
			const top = vp.scrollTop;
			if (atEnd(vp)) pinned.current = true;
			else if (top < last) pinned.current = false;
			last = top;
		};
		const grew = new ResizeObserver(() => {
			if (pinned.current) vp.scrollTop = vp.scrollHeight;
			last = vp.scrollTop;
		});
		grew.observe(body);
		grew.observe(vp);
		vp.addEventListener("scroll", onScroll, { passive: true });
		return () => {
			grew.disconnect();
			vp.removeEventListener("scroll", onScroll);
		};
	}, [follow, viewport, content]);

	useEffect(() => {
		const vp = viewport.current;
		if (!scroll || scroll.seq === applied || !ready || !vp) return;
		let done = false;
		const attempt = () => {
			if (done || !applyScroll(vp, scroll)) return false;
			done = true;
			onApplied(scroll.seq);
			return true;
		};
		if (attempt() || !content.current) return;
		const grew = new ResizeObserver(() => {
			if (attempt()) grew.disconnect();
		});
		grew.observe(content.current);
		return () => grew.disconnect();
	}, [scroll, applied, ready, viewport, content, onApplied]);
}
