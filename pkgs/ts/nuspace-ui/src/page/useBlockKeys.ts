// The page's own keyboard: the block-selection regime.
//
// Only live while at least one block is selected. A focused editor (Monaco, a
// ghost) owns its keys outright and stops them before they reach the page.

import type * as React from "react";
import { useCallback } from "react";
import type { PageModel } from "./model";
import type { FocusReq } from "./state";
import type { Block } from "./types";

export function useBlockKeys(
	{ blocks, editor, patch }: PageModel,
	{
		focusBlock,
		enterBlock,
		deleteBlocks,
		moveSelected,
	}: {
		focusBlock: (block: Block, req: Omit<FocusReq, "blockId">, editing: string[]) => void;
		enterBlock: (block: Block) => void;
		deleteBlocks: (ids: string[]) => void;
		moveSelected: (dir: -1 | 1) => void;
	},
) {
	return useCallback(
		(e: React.KeyboardEvent) => {
			const sel = editor.selected;
			if (sel.length === 0) return;
			const ids = blocks.map((b) => b.id);
			const first = ids.indexOf(sel[0]);
			const last = ids.indexOf(sel[sel.length - 1]);

			if (e.key === "Escape") {
				e.preventDefault();
				patch({ selected: [], anchor: null });
				return;
			}
			if (e.key === "Enter") {
				e.preventDefault();
				const b = blocks[last];
				if (b) enterBlock(b);
				return;
			}
			if (e.key === "Backspace" || e.key === "Delete") {
				e.preventDefault();
				deleteBlocks(sel);
				return;
			}
			if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "a") {
				e.preventDefault();
				patch({ selected: ids, anchor: ids[0] ?? null });
				return;
			}
			if (e.key === "ArrowUp" || e.key === "ArrowDown") {
				e.preventDefault();
				const dir = e.key === "ArrowUp" ? -1 : 1;
				if (e.metaKey || e.ctrlKey) {
					moveSelected(dir);
					return;
				}
				if (e.shiftKey) {
					const anchor = editor.anchor ?? sel[0];
					const a = ids.indexOf(anchor);
					const head = dir < 0 ? first - 1 : last + 1;
					if (head < 0 || head >= ids.length) return;
					const lo = Math.min(a, head);
					const hi = Math.max(a, head);
					patch({ selected: ids.slice(lo, hi + 1), anchor });
					return;
				}
				const j = dir < 0 ? first - 1 : last + 1;
				if (j < 0 || j >= ids.length) return;
				// Land the caret when the neighbour can hold one; otherwise the
				// selection just walks on, carrying the parked column with it.
				focusBlock(
					blocks[j],
					{ place: dir < 0 ? "end" : "start", column: editor.column ?? undefined },
					editor.editing,
				);
				return;
			}
		},
		[
			blocks,
			deleteBlocks,
			editor.anchor,
			editor.column,
			editor.editing,
			editor.selected,
			enterBlock,
			focusBlock,
			moveSelected,
			patch,
		],
	);
}
