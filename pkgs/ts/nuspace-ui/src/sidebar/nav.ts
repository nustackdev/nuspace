// The nav rows' planes: home, search and settings, the system planes that
// always exist. The host seeds each with a fixed id (nuspace.system.ui), and
// the rail draws them in its own group under the top bar, out of the tree and
// out of the pinned: they never move, nest, go or need a shortcut of
// their own.
//
// Settings has a key of its own, cmd/ctrl+comma, the one every app uses.
// Home has cmd/ctrl+shift+H, the browsers' own home key, taken over here.

import { useEffect } from "react";
import { openHere } from "../core/router";
import { SEARCH_PLANE } from "./search";

/** The home Plane's id, fixed by the host. */
export const HOME_PLANE = "home";

/** The settings Plane's id, fixed by the host. */
export const SETTINGS_PLANE = "settings";

/** The planes the nav rows draw, in order. Never a tree row nor a pin. */
export const NAV_PLANES: ReadonlySet<string> = new Set([HOME_PLANE, SEARCH_PLANE, SETTINGS_PLANE]);

/** The home shortcut by key name; the kit `Shortcut` spells it. */
export const HOME_KEYS = ["mod", "shift", "H"] as const;

/** The settings shortcut by key name; the kit `Shortcut` spells it. */
export const SETTINGS_KEYS = ["mod", ","] as const;

/** Open home in the focused pane, or focus it where it is open. */
export function openHome(): void {
	openHere(HOME_PLANE);
}

/** Open settings in the focused pane, or focus it where it is open. */
export function openSettings(): void {
	openHere(SETTINGS_PLANE);
}

/**
 * Cmd/ctrl+comma opens settings from anywhere in the window. Capture, like
 * the new plane key: a cell's editor stops the keys it answers, and this one
 * has to work from inside it too. Mount it once.
 */
export function useSettingsShortcut(): void {
	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			if (e.key !== "," || !(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey) return;
			e.preventDefault();
			openSettings();
		};
		window.addEventListener("keydown", onKey, true);
		return () => window.removeEventListener("keydown", onKey, true);
	}, []);
}

/**
 * Cmd/ctrl+shift+H opens home from anywhere in the window, over the
 * browser's own (home page in Chrome and Safari, history in Firefox).
 * Capture, like the settings key, to work from inside a cell's editor too.
 * Mount it once.
 */
export function useHomeShortcut(): void {
	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			if (e.key.toLowerCase() !== "h" || !(e.metaKey || e.ctrlKey) || e.altKey || !e.shiftKey) {
				return;
			}
			e.preventDefault();
			openHome();
		};
		window.addEventListener("keydown", onKey, true);
		return () => window.removeEventListener("keydown", onKey, true);
	}, []);
}
