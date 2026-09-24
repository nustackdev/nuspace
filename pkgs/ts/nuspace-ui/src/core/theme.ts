// Theme ownership for the shell.
//
// The kit ships both themes (palette.md §2 maps every semantic role twice) and
// flips on a single `.dark` class on <html>. Nothing was flipping it: the
// document hardcoded `class="dark"`, so light was implemented and unreachable.
//
// This module is the one place the class is written. It applies the stored
// preference at import time -- before React mounts, so there is no flash --
// and notifies subscribers on every change, which is how Monaco (the one
// surface that cannot read CSS variables) restains itself.
//
// Not part of the nustd.ui bridge. Purely browser-side, same as the router.

import { useSyncExternalStore } from "react";

export type Theme = "dark" | "light";

const KEY = "nuspace.theme";
const DEFAULT: Theme = "dark";

const subscribers = new Set<() => void>();

function stored(): Theme | null {
	try {
		const v = window.localStorage.getItem(KEY);
		return v === "dark" || v === "light" ? v : null;
	} catch {
		// Private mode / storage disabled. The default is still reachable.
		return null;
	}
}

let current: Theme = stored() ?? DEFAULT;

function paint(theme: Theme): void {
	document.documentElement.classList.toggle("dark", theme === "dark");
	// `color-scheme` is what the browser paints its *own* UI from: scrollbars,
	// the overscroll gutter, form controls, caret. None of that reads our CSS,
	// so without this line the scrollbar stays light in dark mode.
	document.documentElement.style.colorScheme = theme;
}

paint(current);

export function getTheme(): Theme {
	return current;
}

export function setTheme(theme: Theme): void {
	if (theme === current) return;
	current = theme;
	paint(theme);
	try {
		window.localStorage.setItem(KEY, theme);
	} catch {
		// Preference is not persisted; the session still honours it.
	}
	for (const cb of subscribers) cb();
}

export function toggleTheme(): void {
	setTheme(current === "dark" ? "light" : "dark");
}

function subscribe(cb: () => void): () => void {
	subscribers.add(cb);
	return () => subscribers.delete(cb);
}

export function useTheme(): Theme {
	return useSyncExternalStore(subscribe, getTheme, getTheme);
}

/** For non-React consumers (Monaco) that need to restain on a flip. */
export function onThemeChange(cb: (theme: Theme) => void): () => void {
	return subscribe(() => cb(current));
}
