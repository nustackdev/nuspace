// The slash menu's behaviour: what it lists, what a key does to it, and what
// a pick makes. The menu itself only draws (./SlashMenu.tsx); the ghost that
// opened it forwards the keys here. A pick inserts after the ghost, or on a
// stand-in (`replace`, ./state.ts) takes the place of the cell it stood for.

import { useCallback, useMemo } from "react";
import type { PlaneModel } from "../model";
import type { CellSpec } from "../types";
import { slashItems as listed } from "./slash";

export function useSlash(
	{ editor, patch, notify }: PlaneModel,
	cellSpecs: CellSpec[],
	createAfter: (afterId: string | null, name: string) => void,
) {
	const slash = editor.slash;
	const slashItems = useMemo(
		() => (slash ? listed(slash.query, cellSpecs) : []),
		[slash, cellSpecs],
	);

	const pickSlash = useCallback(
		(item: CellSpec) => {
			const s = editor.slash;
			if (!s) return;
			const replace = editor.ghost?.replace;
			patch((e) => ({
				slash: null,
				ghost: null,
				editing: replace ? e.editing.filter((id) => id !== replace) : e.editing,
				leaving: replace ? [...e.leaving, replace] : e.leaving,
			}));
			createAfter(s.cellId, item.name);
			if (replace) notify("cell.delete", { cell_id: replace });
		},
		[createAfter, editor.ghost, editor.slash, notify, patch],
	);

	/** Returns true when the menu consumed the key. */
	const slashKey = useCallback(
		(key: string): boolean => {
			const s = editor.slash;
			if (!s) return false;
			const items = listed(s.query, cellSpecs);
			if (key === "ArrowDown" || key === "ArrowUp") {
				const d = key === "ArrowDown" ? 1 : -1;
				const n = Math.max(1, items.length);
				patch({ slash: { ...s, index: (s.index + d + n) % n } });
				return true;
			}
			if (key === "Enter") {
				const item = items[Math.min(s.index, items.length - 1)];
				if (item) pickSlash(item);
				return true;
			}
			if (key === "Escape") {
				patch({ slash: null });
				return true;
			}
			return false;
		},
		[editor.slash, cellSpecs, patch, pickSlash],
	);

	/** Hover moved the highlight by `d` rows. */
	const moveSlash = useCallback(
		(d: number) =>
			patch((e) => {
				if (!e.slash) return {};
				const n = Math.max(1, slashItems.length);
				return { slash: { ...e.slash, index: (e.slash.index + d + n) % n } };
			}),
		[patch, slashItems.length],
	);

	return { slash, slashItems, pickSlash, slashKey, moveSlash };
}
