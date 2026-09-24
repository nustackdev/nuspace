// Where the caret goes.
//
// Inside a block's open source editor you get a caret. Across a block
// boundary you get *block* selection:
//
//   - Arrowing out of an editor's first or last line moves to the next block
//   - If that block is open in code mode, the caret enters it, carrying its
//     column
//   - Otherwise the block gets *selected* and the page takes keyboard focus

import { useCallback } from "react";
import type { PageModel } from "./model";
import type { FocusReq } from "./state";
import type { Block, ExitDir } from "./types";

export function useFocusRouting({
	blocks,
	editor,
	patch,
	index,
	rootRef,
	elRefs,
	endGhost,
	plusGhost,
}: PageModel) {
	const focusBlock = useCallback(
		(block: Block, req: Omit<FocusReq, "blockId">, editing: string[]) => {
			if (editing.includes(block.id)) {
				patch({
					focus: { blockId: block.id, ...req },
					selected: [],
					anchor: null,
					column: null,
				});
				return;
			}
			// A block with its source closed has no text for a caret to sit in.
			// Select it, and park the column so the next hop still lands under
			// the caret.
			patch({
				focus: null,
				selected: [block.id],
				anchor: block.id,
				column: req.column ?? null,
			});
			rootRef.current?.focus({ preventScroll: true });
			elRefs.current.get(block.id)?.scrollIntoView({ block: "nearest" });
		},
		[patch, rootRef, elRefs],
	);

	/**
	 * Leave a block vertically and land wherever is next.
	 *
	 * A ghost is not in `blocks` -- it is not a block -- but it IS in the
	 * document, between two rows or at the foot of the page, so travel has to
	 * know about it or the last line on every page would be unreachable from
	 * the keyboard. It carries no column: there is no text in it to land under.
	 */
	const step = useCallback(
		(fromId: string, dir: ExitDir, column: number | undefined) => {
			const i = index(fromId);
			if (i < 0) return;
			if (dir === "down") {
				if (editor.ghost === fromId) {
					plusGhost.current?.focus();
					return;
				}
				if (i === blocks.length - 1) {
					endGhost.current?.focus();
					return;
				}
			} else if (i > 0 && editor.ghost === blocks[i - 1].id) {
				plusGhost.current?.focus();
				return;
			}
			const j = dir === "up" ? i - 1 : i + 1;
			if (j < 0 || j >= blocks.length) return;
			focusBlock(blocks[j], { place: dir === "up" ? "end" : "start", column }, editor.editing);
		},
		[blocks, editor.editing, editor.ghost, focusBlock, index, endGhost, plusGhost],
	);

	const enterBlock = useCallback(
		(block: Block, place: "start" | "end" = "end") => {
			patch((e) => ({
				editing: e.editing.includes(block.id) ? e.editing : [...e.editing, block.id],
				focus: { blockId: block.id, place },
				selected: [],
				anchor: null,
			}));
		},
		[patch],
	);

	/** Open or close a block's source editor. The caret follows it open. */
	const setEditing = useCallback(
		(id: string, on: boolean) => {
			patch((e) => ({
				editing: on
					? e.editing.includes(id)
						? e.editing
						: [...e.editing, id]
					: e.editing.filter((x) => x !== id),
				focus: on ? { blockId: id, place: "end" } : e.focus,
			}));
		},
		[patch],
	);

	/** Select one block and hand the keyboard to the page. */
	const selectBlock = useCallback(
		(id: string) => {
			patch({ selected: [id], anchor: id, focus: null });
			rootRef.current?.focus({ preventScroll: true });
		},
		[patch, rootRef],
	);

	return { focusBlock, step, enterBlock, setEditing, selectBlock };
}
