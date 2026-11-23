// The structural ops: save a cell's source, create, remove, reorder.
//
// A create round-trips through the server. The id does not: the browser mints
// it and sends it, so focus is aimed at a known id rather than guessed at from
// a position once `set_cells` comes back.
//
// A create that asks for focus parks its request at once (../focus), and
// the new cell's markdown editor takes it, and whatever text it carries,
// when it takes commands. One that does not is landed on when the server confirms it: an
// empty program opens its source for typing, a cell from a spec is selected
// with a request for its markdown editor, so a cell that draws one gets the caret
// and one that does not stays selected, Enter away from what it draws.
//
// `remove` is the one delete path. Every gesture that deletes cells goes
// through it, so they all hide the cells until the server drops them, close
// their sources, drop their requests, and send the caret where the caller
// says. `withdraw` is the same path in two steps: the cells go out of sight
// now and the delete is sent later, or they come back, for a caller whose
// delete must wait on something else landing first.
//
// The plane is laid out (../layout/model.ts): a reorder sends the whole new
// rows (`layout.set`), never a cell move, and the keyboard moves the rows
// holding the selection, a strip as one. A create sends its rows too, the
// new cell already in place: under a cell of a strip it goes into the
// column under it, at any depth (`withNewCell`). An id taken is tried once
// more under a fresh one (../create.ts).

import type { MarkdownHandle } from "@nustackdev/ui-kit";
import { useCallback, useEffect, useRef } from "react";
import { mintId } from "../../core/ids";
import type { FocusRequest, FocusTarget, Place, PlaneModel } from "../api";
import { awaitCreate, createLanded } from "../create";
import type { Ask } from "../focus/useFocusRouting";
import { rowsInOrder, stepRows, withNewCell } from "../layout/model";
import type { FocusReq, InputLine } from "../state";
import type { LayoutRow } from "../types";

export function useStructure(
	{ cells, layout, patch, read, notify, rootRef, elRefs, index }: PlaneModel,
	{
		request,
		drop,
		focus,
		select,
	}: {
		request: (cellId: string, ask: Ask, landed?: (doc: MarkdownHandle) => void) => number;
		drop: (gone: (r: FocusReq) => boolean) => void;
		focus: (target: FocusTarget) => void;
		select: (ids: string[], anchor?: string) => void;
	},
) {
	/** A cell created with nothing asked for, landed on once it arrives.
	 *  `set_cells` prunes selection naming a cell it does not carry, so this
	 *  waits here rather than in the editor state. */
	const landing = useRef<{ id: string; open: boolean } | null>(null);

	// A create that landed waits for no `Exists` any more.
	useEffect(() => {
		for (const c of cells) createLanded(c.id);
	}, [cells]);

	useEffect(() => {
		const want = landing.current;
		if (!want || !cells.some((b) => b.id === want.id)) return;
		landing.current = null;
		const id = want.id;
		if (want.open) {
			patch((e) => ({
				editing: e.editing.includes(id) ? e.editing : [...e.editing, id],
				selected: [],
				anchor: null,
			}));
			request(id, { to: "source", at: "start" });
			return;
		}
		select([id]);
		patch({ column: null });
		elRefs.current.get(id)?.scrollIntoView({ block: "nearest" });
		request(id, { to: "document", at: "end" });
	}, [cells, patch, request, select, elRefs]);

	const commitSource = useCallback(
		(id: string, source: string) => {
			notify("cell.update", { cell_id: id, source });
		},
		[notify],
	);

	/**
	 * A cell made from the Cell `spec` at `at` (last when its `after` is
	 * gone). The server stores the Cell's program; a name no Cell has makes
	 * the starter program. `line` is the input line feeding the request.
	 * Returns the new id.
	 */
	const create = useCallback(
		(at: Place, spec: string, want?: FocusRequest, line?: InputLine): string => {
			const id = mintId("c");
			const rowsFor = (cell: string): LayoutRow[] => withNewCell(layout, cell, at.after);
			notify("cell.create", { cell_id: id, name: spec, rows: rowsFor(id) });
			// Taken: once more under a fresh id. What waits on this one's id
			// (its focus, its landing) is not moved over.
			awaitCreate(id, () => {
				const again = mintId("c");
				notify("cell.create", { cell_id: again, name: spec, rows: rowsFor(again) });
			});
			if (want) {
				const { landed, ...carry } = want;
				request(id, { ...carry, to: "document", fresh: true, line }, landed);
			} else {
				landing.current = { id, open: spec === "" };
			}
			return id;
		},
		[layout, notify, request],
	);

	/** The cells out of sight: hidden, their sources closed, out of the selection. */
	const hide = useCallback(
		(ids: string[]) => {
			const gone = new Set(ids);
			patch((e) => ({
				editing: e.editing.filter((x) => !gone.has(x)),
				leaving: [...e.leaving, ...ids.filter((x) => !e.leaving.includes(x))],
				selected: e.selected.filter((x) => !gone.has(x)),
				anchor: e.anchor && gone.has(e.anchor) ? null : e.anchor,
			}));
		},
		[patch],
	);

	/** The delete itself: sent, and what waited on the cells let go. */
	const send = useCallback(
		(ids: string[]) => {
			const gone = new Set(ids);
			for (const cell_id of ids) notify("cell.delete", { cell_id });
			drop((r) => gone.has(r.cellId));
		},
		[drop, notify],
	);

	const remove = useCallback(
		(ids: string[], target?: FocusTarget | null) => {
			if (ids.length === 0) return;
			const first = Math.min(...ids.map(index).filter((i) => i >= 0));
			const above = Number.isFinite(first) ? cells[first - 1] : undefined;
			send(ids);
			hide(ids);
			if (target === null) return;
			if (target) {
				focus(target);
				return;
			}
			// The cell above takes the selection, and the plane the keyboard.
			select(above ? [above.id] : []);
			rootRef.current?.focus({ preventScroll: true });
		},
		[cells, focus, hide, index, rootRef, select, send],
	);

	/** Out of sight now; `remove` sends the delete, `restore` shows them again. Either, once. */
	const withdraw = useCallback(
		(ids: string[]) => {
			hide(ids);
			let open = true;
			return {
				remove() {
					if (!open) return;
					open = false;
					send(ids);
				},
				restore() {
					if (!open) return;
					open = false;
					patch((e) => ({ leaving: e.leaving.filter((x) => !ids.includes(x)) }));
				},
			};
		},
		[hide, patch, send],
	);

	const reorder = useCallback(
		(ids: string[]) => {
			const rows = rowsInOrder(layout, ids);
			if (rows) notify("layout.set", { rows });
		},
		[layout, notify],
	);

	/** The rows holding the selected cells one row up or down, as a block. */
	const moveSelected = useCallback(
		(dir: -1 | 1) => {
			const rows = stepRows(layout, read().selected, dir);
			if (rows) notify("layout.set", { rows });
		},
		[layout, read, notify],
	);

	return { commitSource, create, remove, withdraw, reorder, moveSelected };
}
