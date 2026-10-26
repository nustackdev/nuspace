// Search is a Plane: the host seeds it (`search`), and its form cell asks by
// content kind. The rail's Search row and cmd/ctrl+K, from anywhere in the
// window, open it like any other plane.

import { useEffect } from "react";
import { openHere } from "../core/router";

/** The search Plane's id, fixed by the host. */
export const SEARCH_PLANE = "search";

/** The shortcut by key name, for the row's hint; the kit `Shortcut` spells it. */
export const SEARCH_KEYS = ["mod", "K"] as const;

/** Open the search Plane in the focused pane, or focus it where it is open. */
export function openSearch(): void {
	openHere(SEARCH_PLANE);
}

/** Cmd/ctrl+K opens search from anywhere in the window. Mount it once. */
export function useSearchShortcut(): void {
	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			if (e.key.toLowerCase() !== "k" || !(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey) {
				return;
			}
			e.preventDefault();
			openSearch();
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, []);
}
