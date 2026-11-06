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
//   - Enter on a selected cell goes into what it draws: its markdown editor, the
//     caret at its end, else its first field or control. With none, the
//     selection goes.
//
// Focus requests are how anything else asks for the caret: a sugar rule,
// the way back from an input line, a cell just created. A request parks in
// local state (../state.ts) and the cell consumes it when it can, then
// clears it: its markdown editor the moment the kit hands its handle
// (./useEditors.ts), its open source editor once it has a view
// (../cell/Code.tsx). Nothing guesses when a cell might be ready, so there
// is no timer and no watching the DOM. What ends a wait is an event too: the
// cell ships saying it draws nothing, its program dies or stops, or it draws
// and no markdown editor is there under it. Then the cell's requests are
// abandoned, and text an input line fed it goes back into that line
// (`held`, ../state.ts) rather than waiting for an editor that will not
// come. A create the server never answers has no such event (there is no
// error reply for a cell op); Escape in the line drops that one.
//
// At most one request pulls the caret: the newest. Asking again, selecting
// cells, pressing somewhere else, or the caret arriving in an input line
// settles the older ones. A settled request that carries something (text,
// markdown, a hook) still lands there, without the caret; one that carries
// nothing has nothing left to do and goes.

import type { MarkdownHandle } from "@nustackdev/ui-kit";
import { useCallback, useLayoutEffect, useRef } from "react";
import type { Beside, FocusRequest, FocusTarget, PlaneModel } from "../api";
import type { FocusReq, InputLine } from "../state";
import type { Cell, ExitDir } from "../types";
import { FOCUSABLE } from "./focusable";

/** A request as it is asked for: everything but what the core fills in. */
export type Ask = Omit<FocusReq, "id" | "cellId" | "pull" | "ready">;

/** Request ids, unique per tab: the key the hooks are kept under. */
let seq = 0;

export function useFocusRouting(
	{ cells, editor, patch, read, index, editorOf, rootRef, elRefs, endGhost, plusGhost }: PlaneModel,
	{ onTitle }: { onTitle?: (at: "start" | "end") => void },
) {
	/** What a request's caller wants to hear once it lands, by request id. */
	const hooks = useRef(new Map<number, (doc: MarkdownHandle) => void>());

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
		(cellId: string, ask: Ask, landed?: (doc: MarkdownHandle) => void): number => {
			const id = ++seq;
			if (landed) hooks.current.set(id, landed);
			const ready = ask.to === "document" && editorOf(cellId) !== null;
			patch((e) => ({
				requests: [...settle(e.requests), { ...ask, id, cellId, pull: true, ready }],
			}));
			return id;
		},
		[editorOf, patch, settle],
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

	/**
	 * Cell `cellId` will not take its markdown editor requests: they go, and text
	 * an input line was feeding it goes back into that line, one line of it.
	 */
	const abandon = useCallback(
		(cellId: string) => {
			patch((e) => {
				const gone = e.requests.filter((r) => r.cellId === cellId && r.to === "document");
				if (gone.length === 0) return {};
				const held = { ...e.held };
				for (const r of gone) {
					hooks.current.delete(r.id);
					const text = (r.text ?? "").replace(/\n+/g, " ").trim();
					if (r.line && text) held[r.line] = text;
				}
				return { requests: e.requests.filter((r) => !gone.includes(r)), held };
			});
		},
		[patch],
	);

	/** The caret arrived in input line `line`: what it feeds pulls, nothing else does. */
	const wake = useCallback(
		(line: InputLine) => {
			patch((e) => {
				if (!e.requests.some((r) => r.pull || r.line === line)) return {};
				return {
					requests: settle(e.requests, (r) => r.line === line).map((r) =>
						r.line === line ? { ...r, pull: true } : r,
					),
				};
			});
		},
		[patch, settle],
	);

	/** `cellId`'s markdown editor takes commands: its requests are ready. */
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
		const docs = new Map(ready.map((r) => [r.id, editorOf(r.cellId)]));
		patch((e) => ({
			requests: e.requests.flatMap((r) =>
				!docs.has(r.id) ? [r] : docs.get(r.id) ? [] : [{ ...r, ready: false }],
			),
		}));
		for (const r of ready) {
			const doc = docs.get(r.id);
			if (!doc) continue;
			const landed = hooks.current.get(r.id);
			hooks.current.delete(r.id);
			if (r.markdown) doc.append(r.markdown);
			if (r.pull) {
				doc.focus(r.at);
				patch((e) => (e.selected.length ? { selected: [], anchor: null } : {}));
			}
			if (r.text) doc.type(r.text);
			landed?.(doc);
		}
	}, [editor.requests, editorOf, patch]);

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
	 * to its markdown editor, or to its open source when it has none. A cell
	 * with neither right now is landed on the way a new one is: selected, the
	 * request parked for an editor that may still come, so the caret has
	 * somewhere to be either way.
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
			const none = editorOf(id) === null;
			const toSource = none && read().editing.includes(id);
			if (none && !toSource && index(id) >= 0) select([id]);
			request(
				id,
				{
					to: toSource ? "source" : "document",
					at: target.at,
					text: carry?.text,
					markdown: carry?.markdown,
				},
				carry?.landed,
			);
		},
		[editorOf, index, onTitle, read, release, request, rootRef, select],
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

	/**
	 * What the caret meets leaving cell `id` that way, the same picture
	 * `step` travels by: an input line first, then the next cell, and above
	 * the top cell the title. Cells being deleted are already gone from it.
	 */
	const beside = useCallback(
		(id: string, dir: ExitDir): Beside => {
			const i = index(id);
			if (i < 0) return { cell: null, line: false, title: false };
			const { ghost, leaving } = read();
			const d = dir === "up" ? -1 : 1;
			let j = i + d;
			while (cells[j] && leaving.includes(cells[j].id)) j += d;
			const cell = cells[j]?.id ?? null;
			const summoned =
				ghost !== null &&
				plusGhost.current !== null &&
				ghost.after === (dir === "down" ? id : i > 0 ? cells[i - 1].id : null);
			const end = dir === "down" && cell === null && endGhost.current !== null;
			return {
				cell,
				line: summoned || end,
				title: dir === "up" && cell === null && !summoned && onTitle !== undefined,
			};
		},
		[cells, index, read, onTitle, endGhost, plusGhost],
	);

	/** Enter on a selected cell: its markdown editor, else what it draws first. */
	const enterCell = useCallback(
		(cell: Cell) => {
			patch({ selected: [], anchor: null });
			if (editorOf(cell.id)) {
				focus({ cell: cell.id, at: "end" });
				return;
			}
			const el = rootRef.current?.querySelector<HTMLElement>(
				`[data-cell="${cell.id}"] [data-cell-ui] :is(${FOCUSABLE})`,
			);
			if (el) el.focus();
			else rootRef.current?.blur();
		},
		[editorOf, focus, patch, rootRef],
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
		// A line summoned at the top sits between the title and the cells.
		if (read().ghost?.after === null && plusGhost.current) {
			plusGhost.current.focus();
			return true;
		}
		focusCell(cells[0], "start");
		return true;
	}, [cells, focusCell, endGhost, plusGhost, read]);

	return {
		request,
		drop,
		release,
		registered,
		abandon,
		wake,
		focus,
		select,
		focusCell,
		step,
		beside,
		enterCell,
		setEditing,
		enterTop,
	};
}
