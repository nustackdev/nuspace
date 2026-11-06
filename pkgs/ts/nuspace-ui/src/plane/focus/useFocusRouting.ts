// Where the caret goes.
//
// Two ways, kept apart on purpose.
//
// Navigation is the plane's own and is what it always was. Inside a cell's
// open source editor you get a caret; across a cell boundary you get *cell*
// selection:
//
//   - Arrowing out of an editor's first or last line moves to the next cell
//   - If that cell is open in code mode, the caret enters it, carrying its
//     column
//   - Otherwise the cell gets *selected* and the plane takes keyboard focus
//   - Down or Enter at the end of the plane's title lands on the first cell
//   - Enter on a selected cell goes into what it draws: its document, the
//     caret at its end, else its first field or control. With none, the
//     selection goes.
//
// Focus requests are how anything else asks for the caret: a sugar rule,
// the way back from an input line, a cell just created. A request parks in
// local state (../state.ts) and the cell consumes it when it can, then
// clears it: its document the moment it registers with the kit registry
// (./useDocuments.ts), its open source editor once it has a view
// (../cell/Code.tsx). Nothing guesses when a cell might be ready, so there
// is no timer and no watching the DOM, and a request whose cell never draws
// a document simply stays parked until something drops it.
//
// At most one request pulls the caret: the newest. Asking again, selecting
// cells, or pressing somewhere else settles the older ones. A settled
// request that carries something (text, markdown, a hook) still lands
// there, without the caret; one that carries nothing has nothing left to do
// and goes.

import type { DocumentHandle } from "@nustackdev/ui-kit";
import { useCallback, useLayoutEffect, useRef } from "react";
import type { FocusRequest, FocusTarget, PlaneModel } from "../api";
import type { FocusReq } from "../state";
import type { Cell, ExitDir } from "../types";
import { FOCUSABLE } from "./focusable";

/** A request as it is asked for: everything but what the core fills in. */
export type Ask = Omit<FocusReq, "id" | "cellId" | "pull" | "ready">;

/** Request ids, unique per tab: the key the hooks are kept under. */
let seq = 0;

export function useFocusRouting(
	{ cells, editor, patch, read, index, document, rootRef, elRefs, endGhost, plusGhost }: PlaneModel,
	{ onTitle }: { onTitle?: (at: "start" | "end") => void },
) {
	/** What a request's caller wants to hear once it lands, by request id. */
	const hooks = useRef(new Map<number, (doc: DocumentHandle) => void>());

	/** Older requests, settled: they keep what they carry and stop pulling. */
	const settle = useCallback((requests: FocusReq[], keep?: (r: FocusReq) => boolean) => {
		const out: FocusReq[] = [];
		for (const r of requests) {
			if (keep?.(r)) out.push(r);
			else if (r.text || r.markdown || hooks.current.has(r.id)) out.push({ ...r, pull: false });
			else hooks.current.delete(r.id);
		}
		return out;
	}, []);

	/** Park a request for cell `cellId`; the newest one pulls. Returns its id. */
	const request = useCallback(
		(cellId: string, ask: Ask, then?: (doc: DocumentHandle) => void): number => {
			const id = ++seq;
			if (then) hooks.current.set(id, then);
			const ready = ask.to === "document" && document(cellId) !== null;
			patch((e) => ({
				requests: [...settle(e.requests), { ...ask, id, cellId, pull: true, ready }],
			}));
			return id;
		},
		[document, patch, settle],
	);

	/** Drop requests for good, hooks and all. */
	const drop = useCallback(
		(gone: (r: FocusReq) => boolean) => {
			patch((e) => {
				const keep = e.requests.filter((r) => !gone(r));
				if (keep.length === e.requests.length) return {};
				for (const r of e.requests) if (gone(r)) hooks.current.delete(r.id);
				return { requests: keep };
			});
		},
		[patch],
	);

	/** The person went somewhere else: no request pulls the caret any more. */
	const release = useCallback(() => {
		patch((e) => (e.requests.some((r) => r.pull) ? { requests: settle(e.requests) } : {}));
	}, [patch, settle]);

	/** A document registered for `cellId`: its requests are ready. */
	const registered = useCallback(
		(cellId: string) => {
			patch((e) =>
				e.requests.some((r) => r.cellId === cellId && r.to === "document" && !r.ready)
					? {
							requests: e.requests.map((r) =>
								r.cellId === cellId && r.to === "document" ? { ...r, ready: true } : r,
							),
						}
					: {},
			);
		},
		[patch],
	);

	// Consume what is ready, once the cell is drawn: a cell an input line was
	// standing in for shows again in the same render that readies it, and
	// only a drawn editor can take the caret.
	useLayoutEffect(() => {
		const ready = editor.requests.filter((r) => r.to === "document" && r.ready);
		if (ready.length === 0) return;
		// Gone again between registering and now: it waits for the next one.
		const docs = new Map(ready.map((r) => [r.id, document(r.cellId)]));
		patch((e) => ({
			requests: e.requests.flatMap((r) =>
				!docs.has(r.id) ? [r] : docs.get(r.id) ? [] : [{ ...r, ready: false }],
			),
		}));
		for (const r of ready) {
			const doc = docs.get(r.id);
			if (!doc) continue;
			const then = hooks.current.get(r.id);
			hooks.current.delete(r.id);
			if (r.markdown) doc.append(r.markdown);
			if (r.pull) {
				doc.focus(r.at);
				patch((e) => (e.selected.length ? { selected: [], anchor: null } : {}));
			}
			if (r.text) doc.type(r.text);
			then?.(doc);
		}
	}, [editor.requests, document, patch]);

	/** Select these cells and hand the keyboard to the plane. */
	const select = useCallback(
		(ids: string[], anchor?: string) => {
			patch((e) => ({
				selected: ids,
				anchor: anchor ?? ids[0] ?? null,
				requests: settle(e.requests),
			}));
			if (ids.length) rootRef.current?.focus({ preventScroll: true });
		},
		[patch, rootRef, settle],
	);

	/**
	 * A focus request. The title has no request to park: it takes the caret
	 * now, or the plane does where there is no title above it. A cell's goes
	 * to its document, or to its open source when it has no document.
	 */
	const focus = useCallback(
		(target: FocusTarget, carry?: Omit<FocusRequest, "at">) => {
			if ("title" in target) {
				release();
				if (onTitle) onTitle(target.title);
				else rootRef.current?.focus({ preventScroll: true });
				return;
			}
			const id = target.cell;
			const toSource = document(id) === null && read().editing.includes(id);
			request(
				id,
				{
					to: toSource ? "source" : "document",
					at: target.at,
					text: carry?.text,
					markdown: carry?.markdown,
				},
				carry?.then,
			);
		},
		[document, onTitle, read, release, request, rootRef],
	);

	/** Navigation: into the cell's open source, else the cell is selected. */
	const focusCell = useCallback(
		(cell: Cell, place: "start" | "end", column?: number) => {
			if (read().editing.includes(cell.id)) {
				request(cell.id, { to: "source", at: place, column });
				patch({ selected: [], anchor: null, column: null });
				return;
			}
			// A cell with its source closed has no text for a caret to sit in.
			// Select it, and park the column so the next hop still lands under
			// the caret.
			select([cell.id]);
			patch({ column: column ?? null });
			elRefs.current.get(cell.id)?.scrollIntoView({ block: "nearest" });
		},
		[elRefs, patch, read, request, select],
	);

	/**
	 * Leave a cell vertically and land wherever is next. False when there is
	 * nowhere: the top cell, going up.
	 *
	 * An input line is not in `cells` -- it is not a cell -- but it IS in the
	 * document, between two rows or at the foot of the plane, so travel has to
	 * know about it or the last line on every plane would be unreachable from
	 * the keyboard. It carries no column: there is no text in it to land under.
	 */
	const step = useCallback(
		(fromId: string, dir: ExitDir, column?: number): boolean => {
			const i = index(fromId);
			if (i < 0) return false;
			const ghost = read().ghost;
			if (dir === "down") {
				if (ghost?.after === fromId && plusGhost.current) {
					plusGhost.current.focus();
					return true;
				}
				if (i === cells.length - 1) {
					endGhost.current?.focus();
					return endGhost.current !== null;
				}
			} else if (ghost && ghost.after === (i > 0 ? cells[i - 1].id : null) && plusGhost.current) {
				plusGhost.current.focus();
				return true;
			}
			const j = dir === "up" ? i - 1 : i + 1;
			if (j < 0 || j >= cells.length) return false;
			focusCell(cells[j], dir === "up" ? "end" : "start", column);
			return true;
		},
		[cells, focusCell, index, read, endGhost, plusGhost],
	);

	/** Enter on a selected cell: its document, else what it draws first. */
	const enterCell = useCallback(
		(cell: Cell) => {
			patch({ selected: [], anchor: null });
			if (document(cell.id)) {
				focus({ cell: cell.id, at: "end" });
				return;
			}
			const el = rootRef.current?.querySelector<HTMLElement>(
				`[data-cell="${cell.id}"] [data-cell-ui] :is(${FOCUSABLE})`,
			);
			if (el) el.focus();
			else rootRef.current?.blur();
		},
		[document, focus, patch, rootRef],
	);

	/** Open or close a cell's source editor. The caret follows it open. */
	const setEditing = useCallback(
		(id: string, on: boolean) => {
			patch((e) => ({
				editing: on
					? e.editing.includes(id)
						? e.editing
						: [...e.editing, id]
					: e.editing.filter((x) => x !== id),
			}));
			if (on) request(id, { to: "source", at: "end" });
		},
		[patch, request],
	);

	/**
	 * Arrive from the title above: the first cell, or the end line on an
	 * empty plane. False when there is nothing to land in.
	 */
	const enterTop = useCallback((): boolean => {
		if (cells.length === 0) {
			const ghost = endGhost.current;
			if (!ghost) return false;
			ghost.focus();
			return true;
		}
		focusCell(cells[0], "start");
		return true;
	}, [cells, focusCell, endGhost]);

	return {
		request,
		drop,
		release,
		registered,
		focus,
		select,
		focusCell,
		step,
		enterCell,
		setEditing,
		enterTop,
	};
}
