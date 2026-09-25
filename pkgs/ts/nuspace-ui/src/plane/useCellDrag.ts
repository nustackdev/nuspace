// Drag reorder, off a cell's grip. The drop index is found against the live
// cell rows, and one `cell.reorder` goes out on release if it moved.
//
// The grip is a button too: a press that never travels past the slop (see
// ../core/drag.ts) moves nothing and calls `onClick` instead.

import type * as React from "react";
import { useCallback, useRef } from "react";
import { CLICK_SLOP } from "../core/drag";
import type { PlaneModel } from "./model";

export function useCellDrag({ planeId, cells, patch, notify, index, elRefs }: PlaneModel) {
	const dragRef = useRef<{ id: string; at: number } | null>(null);

	const dropIndexFor = useCallback(
		(clientY: number) => {
			let at = cells.length;
			for (let i = 0; i < cells.length; i++) {
				const el = elRefs.current.get(cells[i].id);
				if (!el) continue;
				const r = el.getBoundingClientRect();
				if (clientY < r.top + r.height / 2) {
					at = i;
					break;
				}
			}
			return at;
		},
		[cells, elRefs],
	);

	return useCallback(
		(e: React.PointerEvent, id: string, onClick?: () => void) => {
			if (e.button !== 0) return;
			e.preventDefault();
			(e.target as HTMLElement).setPointerCapture?.(e.pointerId);
			const x0 = e.clientX;
			const y0 = e.clientY;

			const move = (ev: PointerEvent) => {
				const cur = dragRef.current;
				if (!cur) {
					if (Math.abs(ev.clientX - x0) < CLICK_SLOP && Math.abs(ev.clientY - y0) < CLICK_SLOP) {
						return;
					}
					dragRef.current = { id, at: index(id) };
					patch({ drag: { id, at: index(id), y: ev.clientY }, selected: [id], anchor: id });
					return;
				}
				const at = dropIndexFor(ev.clientY);
				dragRef.current = { ...cur, at };
				patch({ drag: { id: cur.id, at, y: ev.clientY } });
			};
			const up = (ev: PointerEvent) => {
				window.removeEventListener("pointermove", move);
				window.removeEventListener("pointerup", up);
				window.removeEventListener("pointercancel", up);
				const cur = dragRef.current;
				dragRef.current = null;
				if (!cur) {
					if (ev.type === "pointerup") onClick?.();
					return;
				}
				patch({ drag: null });
				const from = index(cur.id);
				if (from < 0 || cur.at === from || cur.at === from + 1) return;
				const ids = cells.map((b) => b.id);
				const rest = ids.filter((i) => i !== cur.id);
				const at = cur.at > from ? cur.at - 1 : cur.at;
				rest.splice(at, 0, cur.id);
				notify("cell.reorder", { plane_id: planeId, cell_ids: rest });
			};
			window.addEventListener("pointermove", move);
			window.addEventListener("pointerup", up);
			window.addEventListener("pointercancel", up);
		},
		[cells, dropIndexFor, index, notify, planeId, patch],
	);
}
