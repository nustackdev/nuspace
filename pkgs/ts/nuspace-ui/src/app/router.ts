// The router. A route is which Planes are open, left to right, and nothing
// else.
//
// One segment: /<id1>+<id2>+... A Plane id never contains `+`, so the split
// is unambiguous, and each id is URI-encoded on its own. Bare "/" is a legal
// route and means nothing is open, which is what a tab lands on before anybody
// picks a row. A Plane appears at most once: opening one that is already open
// focuses its pane instead of drawing it twice.
//
// Which pane has focus lives here too, beside the routes, because both the
// sidebar (what a plain click replaces) and the Viewer (which pane is drawn as
// focused) read it. It is not in the URL: back and forward move the panes,
// and focus follows whatever is still open.
//
// Not part of the nustd.ui bridge -- purely browser-side.

import type React from "react";
import { useSyncExternalStore } from "react";

const SEP = "+";

/** The plane ids in `pathname`, left to right. Empty when it names none. */
export function splitRoutes(pathname: string): string[] {
	const parts = pathname.split("/").filter((s) => s.length > 0);
	if (parts.length !== 1) return [];
	const out: string[] = [];
	for (const raw of parts[0].split(SEP)) {
		if (!raw) continue;
		let id: string;
		try {
			id = decodeURIComponent(raw);
		} catch {
			continue;
		}
		if (id && !out.includes(id)) out.push(id);
	}
	return out;
}

/** The Planes the live URL names. Read directly: callable outside a render. */
export function currentRoutes(): string[] {
	return splitRoutes(window.location.pathname);
}

/**
 * The URL a list of Planes resolves to. Exported so the sidebar can render
 * real anchors (kit `NavLink` is an `<a>`): middle-click and the status bar
 * preview work, and the click handler only has to suppress the default
 * navigation.
 */
export function hrefFor(planeIds: string | string[]): string {
	const ids = (Array.isArray(planeIds) ? planeIds : [planeIds]).filter(Boolean);
	return ids.length ? `/${ids.map(encodeURIComponent).join(SEP)}` : "/";
}

// -- the store ---------------------------------------------------------------

const subscribers = new Set<() => void>();

function emit(): void {
	for (const cb of subscribers) cb();
}

function subscribe(cb: () => void): () => void {
	subscribers.add(cb);
	const onPop = () => cb();
	window.addEventListener("popstate", onPop);
	return () => {
		subscribers.delete(cb);
		window.removeEventListener("popstate", onPop);
	};
}

/** The pathname is the snapshot: a string, so it is stable by value. */
function getPath(): string {
	return window.location.pathname;
}

/** The focused Plane as last set, which may since have been closed. */
let focusedRaw = "";

/** The focused pane, resolved against what is open: the last one when the
 *  remembered one is gone, "" when nothing is open. */
function resolveFocus(routes: string[]): string {
	if (focusedRaw && routes.includes(focusedRaw)) return focusedRaw;
	return routes.length ? routes[routes.length - 1] : "";
}

function getFocus(): string {
	return resolveFocus(currentRoutes());
}

// Memoised by pathname, so every caller in a render sees the same array.
let memoPath: string | null = null;
let memoRoutes: string[] = [];

function routesOf(pathname: string): string[] {
	if (pathname !== memoPath) {
		memoPath = pathname;
		memoRoutes = splitRoutes(pathname);
	}
	return memoRoutes;
}

/** The Planes this tab has open, left to right. */
export function useRoutes(): string[] {
	return routesOf(useSyncExternalStore(subscribe, getPath, getPath));
}

/** The focused pane's Plane, or "" when nothing is open. */
export function useFocusedRoute(): string {
	return useSyncExternalStore(subscribe, getFocus, getFocus);
}

// -- moves -------------------------------------------------------------------

function go(ids: string[], replace = false): void {
	const url = hrefFor(ids);
	if (window.location.pathname !== url) {
		if (replace) window.history.replaceState({}, "", url);
		else window.history.pushState({}, "", url);
	}
	emit();
}

/** Mark a pane focused. No history entry: focus is not a place. */
export function focusPane(planeId: string): void {
	if (focusedRaw === planeId) return;
	focusedRaw = planeId;
	emit();
}

/**
 * Put `planeId` in the focused pane, or open the first pane when none is. If
 * it is already open elsewhere, that pane just takes focus.
 */
export function replacePane(planeId: string): void {
	if (!planeId) return;
	const routes = currentRoutes();
	if (routes.includes(planeId)) {
		focusPane(planeId);
		return;
	}
	const at = routes.indexOf(resolveFocus(routes));
	const next = at < 0 ? [planeId] : routes.map((id, i) => (i === at ? planeId : id));
	focusedRaw = planeId;
	go(next);
}

/** Append a pane on the right and focus it. Already open: focus it. */
export function openPane(planeId: string): void {
	if (!planeId) return;
	const routes = currentRoutes();
	focusedRaw = planeId;
	if (routes.includes(planeId)) {
		emit();
		return;
	}
	go([...routes, planeId]);
}

/**
 * Close the panes showing any of `planeIds`. `replace` rewrites the current
 * history entry instead of pushing one, for a Plane that no longer exists and
 * that the back button should not bring back.
 */
export function closePanes(planeIds: string[], replace = false): void {
	const gone = new Set(planeIds);
	const routes = currentRoutes();
	const next = routes.filter((id) => !gone.has(id));
	if (next.length === routes.length) return;
	if (gone.has(focusedRaw)) {
		// Focus moves to the neighbour on the left of the first closed pane,
		// or the new leftmost when that was the first.
		const first = routes.findIndex((id) => gone.has(id));
		const left = routes
			.slice(0, first)
			.reverse()
			.find((id) => !gone.has(id));
		focusedRaw = left ?? next[0] ?? "";
	}
	go(next, replace);
}

/** Close one pane. */
export function closePane(planeId: string): void {
	closePanes([planeId]);
}

function isSplitClick(e: React.MouseEvent<HTMLElement>): boolean {
	return e.metaKey || e.ctrlKey;
}

/**
 * Click handler for an anchor that navigates in-app. A plain click replaces
 * the focused pane, cmd/ctrl-click opens a split. Shift and alt clicks (new
 * window, download) and the middle button are left to the browser.
 */
export function onNavClick(planeId: string) {
	return (e: React.MouseEvent<HTMLElement>) => {
		if (e.defaultPrevented) return;
		if (e.button !== 0 || e.shiftKey || e.altKey) return;
		e.preventDefault();
		if (isSplitClick(e)) openPane(planeId);
		else replacePane(planeId);
	};
}

/**
 * Landing bootstrap. Anything deeper than one segment is not a route, so it
 * becomes the bare "/" rather than a guess at which of its segments was
 * meant. A duplicate or empty id in the list is normalised away.
 */
export function ensureLanding(): void {
	const url = hrefFor(currentRoutes());
	if (window.location.pathname === url) return;
	window.history.replaceState({}, "", url);
	emit();
}
