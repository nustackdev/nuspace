// Whether the rail is folded, and the ways to fold it.
//
// The rail is the first panel of the shell's split (../shell/Shell.tsx), the
// kit's `ResizablePanelGroup`, and the split is the truth: a drag past the
// rail's minimum folds it, Enter on its border flips it, and the buttons and
// cmd/ctrl+\ ask the split through the handle bound here. The split keeps the
// fold, the width and the width to unfold to under RAIL_LAYOUT_KEY.
//
// Two places draw from the fold besides the rail, the shell's reopen button
// and the first pane bar's room for it, so the fold is mirrored in a module
// level store like ../core/theme.ts: the split publishes every change it
// lands.

import { type ResizablePanelGroupHandle, readStored } from "@nustackdev/ui-kit";
import type * as React from "react";
import { useEffect, useSyncExternalStore } from "react";

/** Where the shell's split keeps the rail's layout. */
export const RAIL_LAYOUT_KEY = "nuspace.rail.layout";

/** The rail's place in the split. */
const RAIL = 0;

const subscribers = new Set<() => void>();
let split: React.RefObject<ResizablePanelGroupHandle | null> | null = null;
let current = false;

function subscribe(cb: () => void): () => void {
	subscribers.add(cb);
	return () => subscribers.delete(cb);
}

function getCollapsed(): boolean {
	return current;
}

/** The split's fold changed, or it just mounted: tell whoever draws from it. */
export function publishRail(collapsed: boolean): void {
	if (collapsed === current) return;
	current = collapsed;
	for (const cb of subscribers) cb();
}

/**
 * The shell binds its split here once mounted, and null on the way out. The
 * ref, not the handle: the handle is rebuilt as the split re-renders.
 */
export function bindRail(ref: React.RefObject<ResizablePanelGroupHandle | null> | null): void {
	split = ref;
	const handle = ref?.current;
	if (handle) publishRail(handle.isCollapsed(RAIL));
}

export function setRailCollapsed(collapsed: boolean): void {
	const handle = split?.current;
	if (!handle) return;
	if (collapsed) handle.collapse(RAIL);
	else handle.expand(RAIL);
}

export function toggleRail(): void {
	setRailCollapsed(!(split?.current?.isCollapsed(RAIL) ?? current));
}

export function useRailCollapsed(): boolean {
	return useSyncExternalStore(subscribe, getCollapsed, getCollapsed);
}

/**
 * Before the split, the rail kept its width and its fold under two keys of
 * its own. Carry them over once, into a split `el` that has none yet, then
 * drop them.
 */
export function migrateRail(handle: ResizablePanelGroupHandle, el: HTMLElement | null): void {
	const WIDTH = "nuspace.rail.width";
	const COLLAPSED = "nuspace.rail.collapsed";
	const width = Number(readStored(WIDTH) ?? Number.NaN);
	const folded = readStored(COLLAPSED) === "1";
	if (readStored(RAIL_LAYOUT_KEY) === null) {
		const span = el?.clientWidth ?? 0;
		if (Number.isFinite(width) && span > 0) {
			const pct = (width / span) * 100;
			handle.setLayout([pct, 100 - pct]);
		}
		if (folded) handle.collapse(RAIL);
	}
	for (const key of [WIDTH, COLLAPSED]) {
		try {
			window.localStorage.removeItem(key);
		} catch {
			// Nothing to do: a stale key is only ever read here
		}
	}
}

/** The shortcut by key name, for tooltips; the kit `Shortcut` spells it. */
export const RAIL_KEYS = ["mod", "\\"] as const;

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
		// The rail's own button stays in the DOM while folded, in a panel the
		// split makes inert, so pick the one that can take focus.
		const toggles = document.querySelectorAll<HTMLElement>("[data-rail-toggle]");
		for (const el of toggles) {
			if (el.getClientRects().length > 0 && !el.closest("[inert]")) {
				el.focus();
				return;
			}
		}
	});
}
