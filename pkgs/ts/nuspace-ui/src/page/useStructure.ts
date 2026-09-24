// The structural ops: save a block's source, create, delete, move.
//
// A create round-trips through the server. The id does not: the browser mints
// it and sends it, so focus is aimed at a known id rather than guessed at from
// a position once `set_page` comes back.

import { useCallback, useEffect, useRef } from "react";
import { mintId } from "../app/ids";
import type { PageModel } from "./model";

export function useStructure({ pageId, blocks, editor, patch, notify, index }: PageModel) {
	/** A block that has been asked for but not shipped back yet. `set_page`
	 *  prunes focus pointing at a block it does not carry, so the intent is
	 *  parked here until the block actually arrives. */
	const pendingFocus = useRef<string | null>(null);

	// Land the caret in a newly created block, once the server confirms it.
	useEffect(() => {
		const want = pendingFocus.current;
		if (!want) return;
		if (!blocks.some((b) => b.id === want)) return;
		pendingFocus.current = null;
		patch((e) => ({
			editing: e.editing.includes(want) ? e.editing : [...e.editing, want],
			focus: { blockId: want, place: "start" },
			selected: [],
		}));
	}, [blocks, patch]);

	const commitSource = useCallback(
		(id: string, source: string) => {
			notify("section.update", { page_id: pageId, section_id: id, source });
		},
		[notify, pageId],
	);

	/**
	 * Add a block made from the snippet `name` after `afterId` (or last), and
	 * aim the caret at it. The server stores the snippet's program; a name no
	 * snippet has makes a blank one.
	 */
	const createAfter = useCallback(
		(afterId: string | null, name: string) => {
			const id = mintId("s");
			const at = afterId ? index(afterId) : -1;
			notify("section.create", {
				page_id: pageId,
				section_id: id,
				name,
				index: at < 0 ? blocks.length : at + 1,
			});
			pendingFocus.current = id;
		},
		[blocks.length, index, notify, pageId],
	);

	const deleteBlocks = useCallback(
		(ids: string[]) => {
			if (ids.length === 0) return;
			const first = index(ids[0]);
			const prev = first > 0 ? blocks[first - 1] : null;
			for (const section_id of ids) {
				notify("section.delete", { page_id: pageId, section_id });
			}
			patch({
				selected: prev ? [prev.id] : [],
				anchor: prev ? prev.id : null,
				focus: null,
				editing: editor.editing.filter((e) => !ids.includes(e)),
			});
		},
		[blocks, editor.editing, index, notify, pageId, patch],
	);

	const moveSelected = useCallback(
		(dir: -1 | 1) => {
			const sel = new Set(editor.selected);
			if (sel.size === 0) return;
			const ids = blocks.map((b) => b.id);
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
			notify("section.reorder", { page_id: pageId, section_ids: rest });
		},
		[blocks, editor.selected, notify, pageId],
	);

	return { commitSource, createAfter, deleteBlocks, moveSelected };
}
