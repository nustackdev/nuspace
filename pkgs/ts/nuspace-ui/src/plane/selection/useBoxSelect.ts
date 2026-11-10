// Box selection: press off the cells and drag, and every cell the box
// touches is selected.
//
// It starts anywhere in the pane that is not a cell's box or a control: the
// margins, a gutter's empty lane, between cells, under the last one. A press
// that never travels past the slop is a plain click, which only clears the
// selection. The box is drawn in viewport coordinates and hit-tested against
// the live cell rows on every move.
//
// What it selects is the plane's own cell selection (./state.ts), so the
// keyboard that acts on a selection (./useCellKeys.ts) acts on it too. It
// works on read-only planes, where that keyboard only copies.
//
// A range select starts inside a cell instead (`startRange`): once the
// pointer leaves that cell's row, any text selection goes and the cells from
// that one to the one under the pointer are selected, for as long as the
// drag lasts. The plane starts one from a press in what a cell with a
// document draws, so a text selection dragged out of its document becomes a
// cell selection: a text selection never spans cells.

import { CLICK_SLOP } from "@nustackdev/ui-kit";
import type * as React from "react";
import { useCallback, useState } from "react";
import type { PlaneModel } from "../api";

/** Where a press never starts a box: inside a cell's box, the plane's identity block, or on a control. */
const NO_BOX =
	'[data-cell-body], [data-identity], button, a, input, textarea, select, [contenteditable="true"], [role="menu"], [role="dialog"]';

export type Box = { left: number; top: number; width: number; height: number };

export function useBoxSelect({ cells, patch, rootRef, elRefs }: PlaneModel) {
	const [box, setBox] = useState<Box | null>(null);

	const startBox = useCallback(
		(e: React.PointerEvent) => {
			if (e.button !== 0 || (e.target as Element).closest(NO_BOX)) return;
			patch((ed) => (ed.selected.length ? { selected: [], anchor: null } : {}));
			const x0 = e.clientX;
			const y0 = e.clientY;
			const body = document.body.style;
			const prevSelect = body.userSelect;
			let on = false;

			const move = (ev: PointerEvent) => {
				if (!on) {
					if (Math.abs(ev.clientX - x0) < CLICK_SLOP && Math.abs(ev.clientY - y0) < CLICK_SLOP) {
						return;
					}
					on = true;
					body.userSelect = "none";
					document.getSelection()?.removeAllRanges();
					// The plane takes the keyboard, so the selection's keys reach it.
					rootRef.current?.focus({ preventScroll: true });
				}
				const left = Math.min(x0, ev.clientX);
				const top = Math.min(y0, ev.clientY);
				const right = Math.max(x0, ev.clientX);
				const bottom = Math.max(y0, ev.clientY);
				setBox({ left, top, width: right - left, height: bottom - top });
				const hit = cells
					.filter((c) => {
						const r = elRefs.current.get(c.id)?.getBoundingClientRect();
						return r && r.left < right && r.right > left && r.top < bottom && r.bottom > top;
					})
					.map((c) => c.id);
				patch((ed) =>
					ed.selected.join() === hit.join() ? {} : { selected: hit, anchor: hit[0] ?? null },
				);
			};
			const up = () => {
				window.removeEventListener("pointermove", move);
				window.removeEventListener("pointerup", up);
				window.removeEventListener("pointercancel", up);
				if (on) body.userSelect = prevSelect;
				setBox(null);
			};
			window.addEventListener("pointermove", move);
			window.addEventListener("pointerup", up);
			window.addEventListener("pointercancel", up);
		},
		[cells, elRefs, patch, rootRef],
	);

	const startRange = useCallback(
		(e: React.PointerEvent, id: string) => {
			if (e.button !== 0 || e.shiftKey) return;
			const body = document.body.style;
			const prevSelect = body.userSelect;
			let on = false;

			const move = (ev: PointerEvent) => {
				const own = elRefs.current.get(id)?.getBoundingClientRect();
				if (!own) return;
				if (!on) {
					if (ev.clientY >= own.top && ev.clientY <= own.bottom) return;
					on = true;
					body.userSelect = "none";
					document.getSelection()?.removeAllRanges();
					// The plane takes the keyboard, so the selection's keys reach it.
					rootRef.current?.focus({ preventScroll: true });
				}
				const top = Math.min(own.top, ev.clientY);
				const bottom = Math.max(own.bottom, ev.clientY);
				const hit = cells
					.filter((c) => {
						const r = elRefs.current.get(c.id)?.getBoundingClientRect();
						return r && r.top < bottom && r.bottom > top;
					})
					.map((c) => c.id);
				patch((ed) => (ed.selected.join() === hit.join() ? {} : { selected: hit, anchor: id }));
			};
			const up = () => {
				window.removeEventListener("pointermove", move);
				window.removeEventListener("pointerup", up);
				window.removeEventListener("pointercancel", up);
				if (on) body.userSelect = prevSelect;
			};
			window.addEventListener("pointermove", move);
			window.addEventListener("pointerup", up);
			window.addEventListener("pointercancel", up);
		},
		[cells, elRefs, patch, rootRef],
	);

	return { box, startBox, startRange };
}
