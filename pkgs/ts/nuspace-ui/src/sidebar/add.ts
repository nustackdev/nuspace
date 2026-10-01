// Where an Add plane request goes.
//
// Five things open the same popup: the sidebar header's `+` and cmd/ctrl+alt+N
// from anywhere (a Plane at the top), a row's hover `+` (a child of that row),
// a pane's `...` menu (a child of that pane's Plane) and cmd/ctrl+alt+shift+N
// from anywhere (a child of the Plane you are on, see `currentPlane`). The pane is in the Viewer, not the sidebar, so
// the request is a module level store like the router rather than a prop, and
// the one popup lives with the rail, which holds the registered list.

import { isMac } from "@nustackdev/ui-kit";
import { useEffect, useSyncExternalStore } from "react";
import { focusedRoute } from "../core/router";
import { ROOT_ID } from "./types";

export type AddRequest = {
	/** Where the new Plane hangs: a Plane id, or `ROOT_ID`. */
	parent: string;
	/** The pane to open it in. The focused pane when left out. */
	pane?: string;
};

let request: AddRequest | null = null;
const subscribers = new Set<() => void>();

function emit(): void {
	for (const cb of subscribers) cb();
}

function subscribe(cb: () => void): () => void {
	subscribers.add(cb);
	return () => subscribers.delete(cb);
}

/** The shortcut for a new Plane at the top, by key name; the kit `Shortcut` spells it. */
export const NEW_PLANE_KEYS = ["mod", "alt", "N"] as const;

/** The same with shift, one level down: a new Plane inside the one you are on. */
export const NEW_INSIDE_KEYS = ["mod", "alt", "shift", "N"] as const;

/**
 * Cmd/ctrl+alt+N opens the popup for a Plane at the top, from anywhere, and
 * with shift for one inside the Plane you are on (`currentPlane`). Read
 * off `code`, not `key`: Option+N on a Mac types a dead key, not an N. Off a
 * Mac, not with AltGr held, where ctrl+alt is how a layout types a letter. On
 * a Mac there is no AltGr, and Firefox reports Option as one, so the check
 * would refuse every press there. Mount it once.
 */
export function useNewPlaneShortcut(): void {
	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			if (e.code !== "KeyN" || !(e.metaKey || e.ctrlKey) || !e.altKey) return;
			if (!isMac() && e.getModifierState("AltGraph")) return;
			e.preventDefault();
			// With shift, inside the Plane you are on. With none, the top.
			const parent = e.shiftKey ? currentPlane() : "";
			openAddPlane({ parent: parent || ROOT_ID });
		};
		// Capture: a cell's editor stops the keys it answers, and this one has
		// to work from inside it too.
		window.addEventListener("keydown", onKey, true);
		return () => window.removeEventListener("keydown", onKey, true);
	}, []);
}

/**
 * The Plane you are on: the sidebar row or tab holding the keyboard (each
 * carries `data-plane-id`, and a click puts the keyboard there), else the
 * focused pane's. "" with neither. What "Add plane inside" means everywhere it
 * shows this shortcut: a row's `+`, a row's menu, a tab's menu.
 */
export function currentPlane(): string {
	const held = document.activeElement?.closest<HTMLElement>("[data-plane-id]");
	return held?.dataset.planeId || focusedRoute();
}

/** Open the popup for `req`. */
export function openAddPlane(req: AddRequest): void {
	request = req;
	emit();
}

/** Close it without making anything. */
export function closeAddPlane(): void {
	if (!request) return;
	request = null;
	emit();
}

/** The open request, null while the popup is shut. */
export function useAddRequest(): AddRequest | null {
	return useSyncExternalStore(
		subscribe,
		() => request,
		() => request,
	);
}
