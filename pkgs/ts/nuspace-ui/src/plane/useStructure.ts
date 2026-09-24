// The structural ops: save a cell's source, create, delete, move.
//
// A create round-trips through the server. The id does not: the browser mints
// it and sends it, so focus is aimed at a known id rather than guessed at from
// a position once `set_plane` comes back.

import { useCallback, useEffect, useRef } from "react";
import { mintId } from "../core/ids";
import type { PlaneModel } from "./model";

export function useStructure({ planeId, cells, editor, patch, notify, index }: PlaneModel) {
	/** A cell that has been asked for but not shipped back yet. `set_plane`
	 *  prunes focus pointing at a cell it does not carry, so the intent is
	 *  parked here until the cell actually arrives. */
	const pendingFocus = useRef<string | null>(null);

	// Land the caret in a newly created cell, once the server confirms it.
	useEffect(() => {
		const want = pendingFocus.current;
		if (!want) return;
		if (!cells.some((b) => b.id === want)) return;
		pendingFocus.current = null;
		patch((e) => ({
			editing: e.editing.includes(want) ? e.editing : [...e.editing, want],
			focus: { cellId: want, place: "start" },
			selected: [],
		}));
	}, [cells, patch]);

	const commitSource = useCallback(
		(id: string, source: string) => {
			notify("cell.update", { plane_id: planeId, cell_id: id, source });
		},
		[notify, planeId],
	);

	/**
	 * Add a cell made from the snippet `name` after `afterId` (or last), and
	 * aim the caret at it. The server stores the snippet's program; a name no
	 * snippet has makes a blank one.
	 */
	const createAfter = useCallback(
		(afterId: string | null, name: string) => {
			const id = mintId("c");
			const at = afterId ? index(afterId) : -1;
			notify("cell.create", {
				plane_id: planeId,
				cell_id: id,
				name,
				index: at < 0 ? cells.length : at + 1,
			});
			pendingFocus.current = id;
		},
		[cells.length, index, notify, planeId],
	);

	const deleteCells = useCallback(
		(ids: string[]) => {
			if (ids.length === 0) return;
			const first = index(ids[0]);
			const prev = first > 0 ? cells[first - 1] : null;
			for (const cell_id of ids) {
				notify("cell.delete", { plane_id: planeId, cell_id });
			}
			patch({
				selected: prev ? [prev.id] : [],
				anchor: prev ? prev.id : null,
				focus: null,
				editing: editor.editing.filter((e) => !ids.includes(e)),
			});
		},
		[cells, editor.editing, index, notify, planeId, patch],
	);

	const moveSelected = useCallback(
		(dir: -1 | 1) => {
			const sel = new Set(editor.selected);
			if (sel.size === 0) return;
			const ids = cells.map((b) => b.id);
			const picked = ids.filter((i) => sel.has(i));
			const first = ids.indexOf(picked[0]);
			const last = ids.indexOf(picked[picked.length - 1]);
			if (dir < 0 && first === 0) return;
			if (dir > 0 && last === ids.length - 1) return;
			const rest = ids.filter((i) => !sel.has(i));
			const anchorIdx = dir < 0 ? first - 1 : last + 1;
			const anchorId = ids[anchorIdx];
			const at = rest.indexOf(anchorId) + (dir < 0 ? 0 : 1);
			rest.splice(at, 0, ...picked);
			notify("cell.reorder", { plane_id: planeId, cell_ids: rest });
		},
		[cells, editor.selected, notify, planeId],
	);

	return { commitSource, createAfter, deleteCells, moveSelected };
}
