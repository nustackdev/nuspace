// Roving tabindex for a rail.
//
// A rail is one tab stop and the arrows move inside it. A rail with fifty rows
// is otherwise a hundred and fifty tab stops.
//
// Rows are addressed by `data-rail-key` rather than a ref map: the kit's
// `NavLink` is a plain function component and does not take one, and the key
// query works the same whether the rows came out of a tree or a flat list.

import type * as React from "react";
import { useCallback, useRef, useState } from "react";

export type RailFocus = {
	/** Goes on the `role="tree"` container the rows are queried inside. */
	containerRef: React.RefObject<HTMLDivElement | null>;
	/** The one row that is in the tab order right now. */
	tabKey: string | null;
	/** What a row's `onFocus` calls, so the tab stop follows the caret. */
	setActiveKey: (key: string) => void;
	/** Move focus to a row by key. */
	focusKey: (key: string) => void;
	/** Move focus to a row by position, clamped to the ends of the rail. */
	focusIndex: (index: number) => void;
	/**
	 * The four moves every rail shares: down, up, first, last. Returns whether
	 * it took the event, so a caller can handle the keys it adds on top.
	 */
	handleArrows: (e: React.KeyboardEvent, index: number) => boolean;
};

/**
 * `keys` is the visible rows in render order; `selectedKey` is the row the
 * route has open. The tab stop follows the caret, falls back to the selection,
 * and falls back again to the first row when whatever it was on went away.
 */
export function useRailFocus(keys: string[], selectedKey: string | null): RailFocus {
	const [activeKey, setActiveKey] = useState<string | null>(selectedKey);
	const containerRef = useRef<HTMLDivElement | null>(null);

	const tabKey =
		activeKey !== null && keys.includes(activeKey)
			? activeKey
			: selectedKey !== null && keys.includes(selectedKey)
				? selectedKey
				: (keys[0] ?? null);

	const focusKey = useCallback((key: string) => {
		setActiveKey(key);
		const el = containerRef.current?.querySelector<HTMLElement>(
			`[data-rail-key="${CSS.escape(key)}"]`,
		);
		el?.focus();
	}, []);

	const focusIndex = useCallback(
		(index: number) => {
			const key = keys[Math.max(0, Math.min(keys.length - 1, index))];
			if (key !== undefined) focusKey(key);
		},
		[keys, focusKey],
	);

	const handleArrows = useCallback(
		(e: React.KeyboardEvent, index: number): boolean => {
			switch (e.key) {
				case "ArrowDown":
					e.preventDefault();
					focusIndex(index + 1);
					return true;
				case "ArrowUp":
					e.preventDefault();
					focusIndex(index - 1);
					return true;
				case "Home":
					e.preventDefault();
					focusIndex(0);
					return true;
				case "End":
					e.preventDefault();
					focusIndex(keys.length - 1);
					return true;
				default:
					return false;
			}
		},
		[keys.length, focusIndex],
	);

	return { containerRef, tabKey, setActiveKey, focusKey, focusIndex, handleArrows };
}
