// The slash menu's behaviour: what it lists, what a key does to it, and what
// a pick makes. The menu itself only draws (./SlashMenu.tsx); the ghost that
// opened it forwards the keys here.

import { useCallback, useMemo } from "react";
import type { PlaneModel } from "./model";
import { filterSlash } from "./SlashMenu";
import type { SlashSnippet } from "./types";

export function useSlash(
	{ editor, patch }: PlaneModel,
	snippets: SlashSnippet[],
	createAfter: (afterId: string | null, name: string) => void,
) {
	const slash = editor.slash;
	const slashItems = useMemo(
		() => (slash ? filterSlash(slash.query, snippets) : []),
		[slash, snippets],
	);

	const pickSlash = useCallback(
		(item: SlashSnippet) => {
			const s = editor.slash;
			if (!s) return;
			patch({ slash: null, ghost: null });
			createAfter(s.cellId, item.name);
		},
		[createAfter, editor.slash, patch],
	);

	/** Returns true when the menu consumed the key. */
	const slashKey = useCallback(
		(key: string): boolean => {
			const s = editor.slash;
			if (!s) return false;
			const items = filterSlash(s.query, snippets);
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
		[editor.slash, snippets, patch, pickSlash],
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
