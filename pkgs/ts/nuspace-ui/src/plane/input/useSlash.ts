// The slash menu's behaviour: what it lists, what a key does to it, and what
// a pick makes. The menu itself only draws (./SlashMenu.tsx); the ghost that
// opened it forwards the keys here. A pick inserts after the ghost, or on a
// stand-in (`replace`, ../state.ts) takes the place of the cell it stood for.
// A stand-in is only ever for a blank cell, and the cell may have been
// written meanwhile (another tab, a program): so whether to replace it is
// asked again as the pick lands. Its document still blank, the pick replaces
// it; anything in it, the pick goes in after and the cell comes back as it
// is now. Text is never lost to a pick.

import { useCallback, useMemo } from "react";
import type { Place, PlaneModel } from "../api";
import type { CellSpec } from "../types";
import { slashItems as listed } from "./slash";

export function useSlash(
	{ editor, patch, editorOf }: PlaneModel,
	cellSpecs: CellSpec[],
	{
		create,
		remove,
	}: {
		create: (at: Place, spec: string) => string;
		remove: (ids: string[], focus: null) => void;
	},
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
			patch({ slash: null, ghost: null });
			create({ after: s.cellId }, item.name);
			// The new cell is landed on, so the replaced one leaves the caret alone.
			if (replace && editorOf(replace)?.blank() === true) remove([replace], null);
		},
		[create, editorOf, editor.ghost, editor.slash, patch, remove],
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
