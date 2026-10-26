// Roving tabindex for the rail's body.
//
// The body is one tab stop and the arrows move through every row in it, in
// the order they are drawn: the nav rows, the pinned, New plane, the tree,
// the extensions. Down off the last wraps to the first. A body with fifty
// rows is otherwise a hundred and fifty tab stops. Section headers are not
// rows: the arrows pass them by.
//
// Mounted once, in ./Rail.tsx, and handed to every section through
// `RailFocusContext`; each row reads it with `useRailNav`.
//
// Rows are addressed by `data-rail-key` rather than a ref map: the kit's
// `NavLink` is a plain function component and does not take one, and the key
// query works the same whether the rows came out of a tree or a flat list.

import type * as React from "react";
import { createContext, useCallback, useContext, useRef, useState } from "react";

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
	 * The four moves every rail shares: down, up, first, last. Down off the
	 * last row wraps round to the first, up off the first to the last, nested
	 * rows included since `keys` is every visible row. Returns whether
	 * it took the event, so a caller can handle the keys it adds on top.
	 */
	handleArrows: (e: React.KeyboardEvent, index: number) => boolean;
	/** `handleArrows` for the row at `key`. */
	arrows: (e: React.KeyboardEvent, key: string) => boolean;
	/**
	 * The body's click: it moves the keyboard into the body without putting
	 * it on a row, so nothing shows focused until a key is pressed. The body
	 * itself takes the focus; a clicked row becomes the tab stop, so the next
	 * arrow carries on from it (`onKeyDown`). A click on a row's own control
	 * keeps that control's focus. Without this a click on empty space only
	 * drops the focus, sending the next Tab to the bottom bar.
	 */
	onClick: (e: React.MouseEvent<HTMLElement>) => void;
	/** The body's own keys, while it holds the focus itself: the arrows, as if on the tab stop. */
	onKeyDown: (e: React.KeyboardEvent<HTMLElement>) => void;
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
					focusIndex((index + 1) % keys.length);
					return true;
				case "ArrowUp":
					e.preventDefault();
					focusIndex((index - 1 + keys.length) % keys.length);
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

	const arrows = useCallback(
		(e: React.KeyboardEvent, key: string) => {
			const index = keys.indexOf(key);
			return index >= 0 && handleArrows(e, index);
		},
		[keys, handleArrows],
	);

	const onClick = useCallback((e: React.MouseEvent<HTMLElement>) => {
		const target = e.target as HTMLElement;
		const row = target.closest<HTMLElement>("[data-rail-key]");
		const control = target.closest("button, input");
		if (row && control && control !== row) return;
		if (row?.dataset.railKey) setActiveKey(row.dataset.railKey);
		e.currentTarget.focus({ preventScroll: true });
	}, []);

	const onKeyDown = useCallback(
		(e: React.KeyboardEvent<HTMLElement>) => {
			if (e.target !== e.currentTarget || tabKey === null) return;
			handleArrows(e, keys.indexOf(tabKey));
		},
		[keys, tabKey, handleArrows],
	);

	return {
		containerRef,
		tabKey,
		setActiveKey,
		focusKey,
		focusIndex,
		handleArrows,
		arrows,
		onClick,
		onKeyDown,
	};
}

/** The body's one focus, from ./Rail.tsx. */
export const RailFocusContext = createContext<RailFocus | null>(null);

/** The rail body's focus, from a row inside it. */
export function useRailNav(): RailFocus {
	const nav = useContext(RailFocusContext);
	if (!nav) throw new Error("useRailNav outside the rail body");
	return nav;
}

/** The body's row keys that are not a tree row's plane id, so no two rows share one. */
export const navKey = (id: string) => `nav:${id}`;
export const pinKey = (id: string) => `pin:${id}`;
export const NEW_PLANE_KEY = "new-plane";
