// The structural ops: save a cell's source, create, delete, move.
//
// A create round-trips through the server. The id does not: the browser mints
// it and sends it, so focus is aimed at a known id rather than guessed at from
// a position once `set_plane` comes back.
//
// A snippet's cell is landed on selected, and then handed what it draws: the
// first focusable thing its program puts up takes the keyboard, a text
// surface with the caret at its end. Drawing takes a run, so the cell is
// watched until something arrives. The watch ends when the hand off happens,
// the moment the person does anything else (another cell selected, the caret
// somewhere, focus gone from the plane), or after HAND_WAIT. A cell that draws
// nothing to focus by then stays selected, which it already is.

import { useCallback, useEffect, useRef, useState } from "react";
import { mintId } from "../core/ids";
import { EDITABLE, placeCaret } from "./Draft";
import type { PlaneModel } from "./model";

/** How long a landed cell is watched for something to focus, in ms. */
const HAND_WAIT = 1500;

/** What a drawn cell can hand the keyboard to. */
const FOCUSABLE = [EDITABLE, "select", "button", "a[href]", '[tabindex]:not([tabindex="-1"])']
	.map((s) => `${s}:not([disabled])`)
	.join(", ");

export function useStructure({
	planeId,
	cells,
	editor,
	patch,
	notify,
	index,
	rootRef,
	elRefs,
}: PlaneModel) {
	/** A cell that has been asked for but not shipped back yet. `set_plane`
	 *  prunes focus pointing at a cell it does not carry, so the intent is
	 *  parked here until the cell actually arrives. */
	const pendingFocus = useRef<{ id: string; open: boolean } | null>(null);
	/** A landed cell waiting to hand the keyboard to what it draws. */
	const [handing, setHanding] = useState<string | null>(null);
	/** When the watch on `handing` gives up, fixed at landing so a re-run keeps it. */
	const handUntil = useRef(0);

	// Land on a newly created cell once the server confirms it. A snippet's
	// cell is selected with its source closed: what it draws is the point. A
	// blank cell has nothing to draw yet, so its source opens for typing.
	useEffect(() => {
		const want = pendingFocus.current;
		if (!want) return;
		if (!cells.some((b) => b.id === want.id)) return;
		pendingFocus.current = null;
		const id = want.id;
		if (want.open) {
			patch((e) => ({
				editing: e.editing.includes(id) ? e.editing : [...e.editing, id],
				focus: { cellId: id, place: "start" },
				selected: [],
			}));
			return;
		}
		patch({ focus: null, selected: [id], anchor: id, column: null });
		rootRef.current?.focus({ preventScroll: true });
		elRefs.current.get(id)?.scrollIntoView({ block: "nearest" });
		handUntil.current = performance.now() + HAND_WAIT;
		setHanding(id);
	}, [cells, patch, rootRef, elRefs]);

	// Hand a landed cell's keyboard to what it draws, once it draws it.
	useEffect(() => {
		if (!handing) return;
		const id = handing;
		const root = rootRef.current;
		const still =
			editor.selected.length === 1 && editor.selected[0] === id && editor.focus === null;
		if (!root || !still) {
			setHanding(null);
			return;
		}
		const handoff = (): boolean => {
			if (document.activeElement !== root) {
				setHanding(null);
				return true;
			}
			const el = root.querySelector<HTMLElement>(
				`[data-cell="${id}"] [data-cell-ui] :is(${FOCUSABLE})`,
			);
			if (!el) return false;
			if (el.matches(EDITABLE)) placeCaret(el, "end");
			else el.focus();
			patch({ selected: [], anchor: null });
			setHanding(null);
			return true;
		};
		if (handoff()) return;
		const seen = new MutationObserver(() => {
			if (handoff()) seen.disconnect();
		});
		const done = window.setTimeout(() => {
			seen.disconnect();
			setHanding(null);
		}, handUntil.current - performance.now());
		seen.observe(root, {
			childList: true,
			subtree: true,
			attributes: true,
			attributeFilter: ["tabindex", "contenteditable", "disabled"],
		});
		return () => {
			seen.disconnect();
			window.clearTimeout(done);
		};
	}, [handing, editor.selected, editor.focus, patch, rootRef]);

	const commitSource = useCallback(
		(id: string, source: string) => {
			notify("cell.update", { cell_id: id, source });
		},
		[notify],
	);

	/**
	 * Add a cell made from the snippet `name` after `afterId` (at the top when
	 * null, or last when `afterId` is gone), and land on it unless `land` is
	 * off. The server stores the snippet's program; a name no snippet has
	 * makes a blank one. Returns the new id.
	 */
	const createAfter = useCallback(
		(afterId: string | null, name: string, land = true): string => {
			const id = mintId("c");
			const at = afterId ? index(afterId) : -1;
			notify("cell.create", {
				plane_id: planeId,
				cell_id: id,
				name,
				index: afterId === null ? 0 : at < 0 ? cells.length : at + 1,
			});
			if (land) pendingFocus.current = { id, open: name === "" };
			return id;
		},
		[cells.length, index, notify, planeId],
	);

	const deleteCells = useCallback(
		(ids: string[]) => {
			if (ids.length === 0) return;
			const first = index(ids[0]);
			const prev = first > 0 ? cells[first - 1] : null;
			for (const cell_id of ids) {
				notify("cell.delete", { cell_id });
			}
			patch({
				selected: prev ? [prev.id] : [],
				anchor: prev ? prev.id : null,
				focus: null,
				editing: editor.editing.filter((e) => !ids.includes(e)),
			});
		},
		[cells, editor.editing, index, notify, patch],
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
