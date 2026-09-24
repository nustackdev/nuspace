// Whether the rail is collapsed. Hidden fully, and brought back from a button
// in the main strip's top left corner or with cmd/ctrl+\.
//
// Two places read it, the rail and the shell (which draws the reopen button),
// so it is a module level store like ../core/theme.ts rather than a hook's
// own state. It lands in localStorage on every change, so a reload keeps it.
// Storage can be missing or throw (private window, blocked site data), so
// every read and write is guarded and the rail falls back to open, the same
// as ./useRailWidth.ts.

import { useEffect, useSyncExternalStore } from "react";

const KEY = "nuspace.rail.collapsed";

const subscribers = new Set<() => void>();

function load(): boolean {
	try {
		return window.localStorage.getItem(KEY) === "1";
	} catch {
		return false;
	}
}

function save(collapsed: boolean): void {
	try {
		window.localStorage.setItem(KEY, collapsed ? "1" : "0");
	} catch {
		// Nothing to do: the state just will not survive a reload
	}
}

let current = load();

function subscribe(cb: () => void): () => void {
	subscribers.add(cb);
	return () => subscribers.delete(cb);
}

function getCollapsed(): boolean {
	return current;
}

export function setRailCollapsed(collapsed: boolean): void {
	if (collapsed === current) return;
	current = collapsed;
	save(collapsed);
	for (const cb of subscribers) cb();
}

export function toggleRail(): void {
	setRailCollapsed(!current);
}

export function useRailCollapsed(): boolean {
	return useSyncExternalStore(subscribe, getCollapsed, getCollapsed);
}

/** The shortcut, for tooltips. */
export const RAIL_SHORTCUT =
	typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent)
		? "⌘\\"
		: "Ctrl+\\";

/** Cmd/ctrl+\ flips the rail from anywhere in the window. Mount it once. */
export function useRailShortcut(): void {
	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			if (e.key !== "\\" || !(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey) return;
			e.preventDefault();
			toggleRail();
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, []);
}

/**
 * Move focus to the button that undoes a flip, after React has drawn it, so a
 * keyboard user is not dropped on the body when the button they pressed hides.
 */
export function focusRailToggle(): void {
	requestAnimationFrame(() => {
		// The rail's own button stays in the DOM while hidden, so pick the one
		// that is drawn.
		const toggles = document.querySelectorAll<HTMLElement>("[data-rail-toggle]");
		for (const el of toggles) {
			if (el.getClientRects().length > 0) {
				el.focus();
				return;
			}
		}
	});
}
