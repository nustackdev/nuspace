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

import type { ResizablePanelGroupHandle } from "@nustackdev/ui-kit";
import type * as React from "react";
import { useEffect } from "react";

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

export function setSidebarCollapsed(collapsed: boolean): void {
	const handle = split?.current;
	if (!handle) return;
	if (collapsed) handle.collapse(SIDEBAR);
	else handle.expand(SIDEBAR);
}

export function toggleSidebar(): void {
	setSidebarCollapsed(!(split?.current?.isCollapsed(SIDEBAR) ?? current));
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
