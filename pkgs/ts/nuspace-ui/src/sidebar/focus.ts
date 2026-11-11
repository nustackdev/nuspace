// The sidebar body's one tab stop.
//
// The body is one tab stop and the arrows move through every row in it, in
// the order they are drawn: the nav section, the desk folders, New plane,
// the Planes tree, the Specs. A body with fifty rows is otherwise
// fifty tab stops. Section titles are not rows: the arrows pass them by.
//
// The kit's roving focus (`useRovingFocus`), with what the sidebar adds on
// top: `arrows` by row key, and the body's own click and keys. Mounted once,
// in ./Sidebar.tsx, and handed to every section through
// `SidebarFocusContext`; each row reads it with `useSidebarNav`. A row carries
// the kit's `ROVING_KEY` attribute.

import { ROVING_KEY, type RovingFocus, useRovingFocus } from "@nustackdev/ui-kit";
import type * as React from "react";
import { createContext, useCallback, useContext } from "react";

export type SidebarFocus = RovingFocus & {
	/** `handleArrows` for the row at `key`. Returns whether it took the event. */
	arrows: (e: React.KeyboardEvent, key: string) => boolean;
	/**
	 * The body's click: it moves the keyboard into the body without putting
	 * it on a row, so nothing shows focused until a key is pressed. A clicked
	 * row becomes the tab stop, so the next arrow carries on from it. A click
	 * on a row's own control keeps that control's focus.
	 */
	onClick: (e: React.MouseEvent<HTMLElement>) => void;
	/** The body's own keys, while it holds the focus itself: the arrows, as if on the tab stop. */
	onKeyDown: (e: React.KeyboardEvent<HTMLElement>) => void;
};

/** `keys` is every row in render order; `selectedKey` the row the focused pane has open. */
export function useSidebarFocus(keys: string[], selectedKey: string | null): SidebarFocus {
	const roving = useRovingFocus(keys, selectedKey);
	const { tabKey, setActiveKey, handleArrows } = roving;

	const arrows = useCallback(
		(e: React.KeyboardEvent, key: string) => {
			const index = keys.indexOf(key);
			return index >= 0 && handleArrows(e, index);
		},
		[keys, handleArrows],
	);

	const onClick = useCallback(
		(e: React.MouseEvent<HTMLElement>) => {
			const target = e.target as HTMLElement;
			const row = target.closest<HTMLElement>(`[${ROVING_KEY}]`);
			const control = target.closest("button, input");
			if (row && control && control !== row) return;
			const key = row?.getAttribute(ROVING_KEY);
			if (key) setActiveKey(key);
			e.currentTarget.focus({ preventScroll: true });
		},
		[setActiveKey],
	);

	const onKeyDown = useCallback(
		(e: React.KeyboardEvent<HTMLElement>) => {
			if (e.target !== e.currentTarget || tabKey === null) return;
			handleArrows(e, keys.indexOf(tabKey));
		},
		[keys, tabKey, handleArrows],
	);

	return { ...roving, arrows, onClick, onKeyDown };
}

/** The body's one focus, from ./Sidebar.tsx. */
export const SidebarFocusContext = createContext<SidebarFocus | null>(null);

/** The sidebar body's focus, from a row inside it. */
export function useSidebarNav(): SidebarFocus {
	const nav = useContext(SidebarFocusContext);
	if (!nav) throw new Error("useSidebarNav outside the sidebar body");
	return nav;
}

/** Row keys that are not a tree row's plane id, so no two rows share one. */
export const navKey = (role: string) => `nav:${role}`;
export const NEW_PLANE_KEY = "new-plane";
