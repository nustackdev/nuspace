// Whether the sidebar is folded, and the ways to fold it.
//
// The sidebar is the first panel of the shell's split (../shell/Shell.tsx),
// the kit's `ResizablePanelGroup`, and the split is the truth: a drag past the
// sidebar's minimum folds it, Enter on its border flips it, and the buttons
// and cmd/ctrl+\ ask the split through the handle bound here. The split keeps
// the fold, the width and the width to unfold to under SIDEBAR_LAYOUT_KEY.
//
// The fold is mirrored here, so the toggle knows which way to flip before the
// split is bound: the split publishes every change it lands. What the panel
// shows (sidebar or rail) does not read it: it follows the panel's own state,
// live through a drag.
//
// ## Narrow
//
// A window narrower than `SIDEBAR_NARROW_PX` has no room for the sidebar
// beside the desk. There the sidebar is always its rail, and opening it lays
// the sidebar over the desk instead (the overlay), closed again by the same
// toggles, Escape, a click beside it or a navigation. The split is left alone
// the whole time: nothing narrow folds, unfolds or saves it, so the width
// and the fold it holds are exactly what a wide window gets back. Every
// toggle goes through here, so each one asks the right one of the two.
//
// Narrow is read off the window, live: a resize across the line switches
// mode, and leaving narrow closes the overlay.

import type { ResizablePanelGroupHandle } from "@nustackdev/ui-kit";
import type * as React from "react";
import { useEffect, useSyncExternalStore } from "react";

/** Where the shell's split keeps the sidebar's layout. */
export const SIDEBAR_LAYOUT_KEY = "nuspace.sidebar.layout";

/** The sidebar's place in the split. */
const SIDEBAR = 0;

let split: React.RefObject<ResizablePanelGroupHandle | null> | null = null;
let current = false;

/** The split's fold changed, or it just mounted. */
export function publishSidebar(collapsed: boolean): void {
	current = collapsed;
}

/**
 * The shell binds its split here once mounted, and null on the way out. The
 * ref, not the handle: the handle is rebuilt as the split re-renders.
 */
export function bindSidebar(ref: React.RefObject<ResizablePanelGroupHandle | null> | null): void {
	split = ref;
	const handle = ref?.current;
	if (handle) publishSidebar(handle.isCollapsed(SIDEBAR));
}

// -- Narrow and the overlay ---------------------------------------------------

/**
 * Below this window width the sidebar is the rail, and opens over the desk:
 * the usual phone line, Tailwind's `sm` (640), the reading measure as well.
 */
export const SIDEBAR_NARROW_PX = 640;

/** The media query for a narrow window. */
export const NARROW_QUERY = `(max-width: ${SIDEBAR_NARROW_PX - 0.02}px)`;

let narrow = readNarrow();
let overlay = false;
const subscribers = new Set<() => void>();
let unwatch: (() => void) | null = null;

function readNarrow(): boolean {
	return typeof window !== "undefined" && !!window.matchMedia?.(NARROW_QUERY).matches;
}

function emit(): void {
	for (const cb of [...subscribers]) cb();
}

/** Follow the window across the line while anything listens. */
function subscribe(cb: () => void): () => void {
	subscribers.add(cb);
	if (!unwatch && typeof window !== "undefined" && window.matchMedia) {
		const query = window.matchMedia(NARROW_QUERY);
		const onChange = () => setSidebarNarrow(query.matches);
		query.addEventListener("change", onChange);
		unwatch = () => query.removeEventListener("change", onChange);
		setSidebarNarrow(query.matches);
	}
	return () => {
		subscribers.delete(cb);
		if (subscribers.size === 0) {
			unwatch?.();
			unwatch = null;
		}
	};
}

/** The window crossed the line (or a test says it did). Leaving narrow closes the overlay. */
export function setSidebarNarrow(next: boolean): void {
	if (next === narrow) return;
	narrow = next;
	if (!narrow) overlay = false;
	emit();
}

/** Whether the window is narrow: the sidebar is the rail and opens as the overlay. */
export function isSidebarNarrow(): boolean {
	return narrow;
}

/** Whether the overlay is open. */
export function isSidebarOverlay(): boolean {
	return overlay;
}

/** Open or close the overlay. Only a narrow window has one. */
export function setSidebarOverlay(open: boolean): void {
	const next = open && narrow;
	if (next === overlay) return;
	overlay = next;
	emit();
}

/** Whether the window is narrow, re-rendering as it crosses the line. */
export function useSidebarNarrow(): boolean {
	return useSyncExternalStore(
		subscribe,
		() => narrow,
		() => false,
	);
}

/** Whether the overlay is open. */
export function useSidebarOverlay(): boolean {
	return useSyncExternalStore(
		subscribe,
		() => overlay,
		() => false,
	);
}

// -- Every toggle --------------------------------------------------------------

/** Fold or unfold: the overlay in a narrow window, the split in a wide one. */
export function setSidebarCollapsed(collapsed: boolean): void {
	if (narrow) {
		setSidebarOverlay(!collapsed);
		return;
	}
	const handle = split?.current;
	if (!handle) return;
	if (collapsed) handle.collapse(SIDEBAR);
	else handle.expand(SIDEBAR);
}

export function toggleSidebar(): void {
	if (narrow) setSidebarOverlay(!overlay);
	else setSidebarCollapsed(!(split?.current?.isCollapsed(SIDEBAR) ?? current));
}

/** The shortcut by key name, for tooltips; the kit `Shortcut` spells it. */
export const SIDEBAR_KEYS = ["mod", "\\"] as const;

/** Cmd/ctrl+\ flips the sidebar from anywhere in the window. Mount it once. */
export function useSidebarShortcut(): void {
	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			if (e.key !== "\\" || !(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey) return;
			e.preventDefault();
			toggleSidebar();
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, []);
}

/**
 * Move focus to the button that reverses a flip, after React has drawn it, so a
 * keyboard user is not dropped on the body when the button they pressed hides.
 */
export function focusSidebarToggle(): void {
	requestAnimationFrame(() => {
		// The header's own button stays in the DOM while folded, in a panel
		// the split makes inert, so pick the one that can take focus.
		const toggles = document.querySelectorAll<HTMLElement>("[data-sidebar-toggle]");
		for (const el of toggles) {
			if (el.getClientRects().length > 0 && !el.closest("[inert]")) {
				el.focus();
				return;
			}
		}
	});
}
