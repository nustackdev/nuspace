// Drag reorder, off a block's grip. The drop index is found against the live
// block rows, and one `section.reorder` goes out on release if it moved.

import type * as React from "react";
import { useCallback, useRef } from "react";
import type { PageModel } from "./model";

export function useBlockDrag({ pageId, blocks, patch, notify, index, elRefs }: PageModel) {
	const dragRef = useRef<{ id: string; at: number } | null>(null);

	const dropIndexFor = useCallback(
		(clientY: number) => {
			let at = blocks.length;
			for (let i = 0; i < blocks.length; i++) {
				const el = elRefs.current.get(blocks[i].id);
				if (!el) continue;
				const r = el.getBoundingClientRect();
				if (clientY < r.top + r.height / 2) {
					at = i;
					break;
				}
			}
			return at;
		},
		[blocks, elRefs],
	);

	return useCallback(
		(e: React.PointerEvent, id: string) => {
			e.preventDefault();
			(e.target as HTMLElement).setPointerCapture?.(e.pointerId);
			dragRef.current = { id, at: index(id) };
			patch({
				drag: { id, at: index(id), y: e.clientY },
				selected: [id],
				anchor: id,
			});

			const move = (ev: PointerEvent) => {
				const at = dropIndexFor(ev.clientY);
				const cur = dragRef.current;
				if (!cur) return;
				dragRef.current = { ...cur, at };
				patch({ drag: { id: cur.id, at, y: ev.clientY } });
			};
			const up = () => {
				window.removeEventListener("pointermove", move);
				window.removeEventListener("pointerup", up);
				const cur = dragRef.current;
				dragRef.current = null;
				patch({ drag: null });
				if (!cur) return;
				const from = index(cur.id);
				if (from < 0 || cur.at === from || cur.at === from + 1) return;
				const ids = blocks.map((b) => b.id);
				const rest = ids.filter((i) => i !== cur.id);
				const at = cur.at > from ? cur.at - 1 : cur.at;
				rest.splice(at, 0, cur.id);
				notify("section.reorder", { page_id: pageId, section_ids: rest });
			};
			window.addEventListener("pointermove", move);
			window.addEventListener("pointerup", up);
		},
		[blocks, dropIndexFor, index, notify, pageId, patch],
	);
}
