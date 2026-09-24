// The router. A route is which Planes are open, left to right, and nothing
// else.
//
// One segment: /<id1>+<id2>+... A Plane id never contains `+`, so the split
// is unambiguous, and each id is URI-encoded on its own. Bare "/" is home: the
// routes ["home"], the Plane the host seeds at open, and what closing the last
// pane lands on. "/home" names the same thing and is written back as "/". A
// Plane appears at most once: opening one that is already open focuses its
// pane instead of drawing it twice.
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

/** The home Plane's id, fixed by the host. What bare "/" opens. */
export const HOME = "home";

/** The plane ids in `pathname`, left to right. Home when it names none. */
export function splitRoutes(pathname: string): string[] {
	const parts = pathname.split("/").filter((s) => s.length > 0);
	if (parts.length !== 1) return [HOME];
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
	return out.length ? out : [HOME];
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
	if (ids.length === 0 || (ids.length === 1 && ids[0] === HOME)) return "/";
	return `/${ids.map(encodeURIComponent).join(SEP)}`;
}

/**
 * The routes a same-origin href names, or null when it is not a route: another
 * origin, more than one path segment, or anything after the path (a query or
 * a hash is left to the browser). Bare "/" is home.
 */
export function routesOfHref(href: string): string[] | null {
	let url: URL;
	try {
		url = new URL(href, window.location.href);
	} catch {
		return null;
	}
	if (url.origin !== window.location.origin || url.search || url.hash) return null;
	if (url.pathname.split("/").filter(Boolean).length > 1) return null;
	return splitRoutes(url.pathname);
}

// -- The store ---------------------------------------------------------------

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

// -- Moves -------------------------------------------------------------------

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

/** Home alone, in one pane: where bare "/" lands. */
export function goHome(): void {
	focusedRaw = HOME;
	go([HOME]);
}

/**
 * Follow a list of Planes the way the sidebar follows one: a plain click puts
 * a single Plane in the focused pane and replaces the panes with a longer
 * list, a split click appends each as a pane of its own.
 */
export function followRoutes(ids: string[], split: boolean): void {
	if (split) {
		for (const id of ids) openPane(id);
		return;
	}
	if (ids.length === 1) {
		replacePane(ids[0]);
		return;
	}
	focusedRaw = ids[ids.length - 1] ?? "";
	go(ids);
}

type Click = Pick<MouseEvent, "button" | "shiftKey" | "altKey" | "metaKey" | "ctrlKey">;

/** A primary click with no modifier the browser owns (shift, alt). */
export function isNavClick(e: Click): boolean {
	return e.button === 0 && !e.shiftKey && !e.altKey;
}

function isSplitClick(e: Click): boolean {
	return e.metaKey || e.ctrlKey;
}

/**
 * Route a click on an anchor inside a cell's ui through the router, so a
 * same-origin link to /<id> or /<a>+<b> switches panes instead of reloading
 * the plane. Cmd/ctrl-click opens a split, as in the sidebar. Returns whether
 * it took the click; anything else (another origin, `_blank`, a download, a
 * modifier the browser owns) is left alone.
 */
export function routeAnchorClick(e: MouseEvent): boolean {
	if (e.defaultPrevented || !isNavClick(e)) return false;
	const target = e.target instanceof Element ? e.target : null;
	const anchor = target?.closest("a[href]");
	if (!(anchor instanceof HTMLAnchorElement)) return false;
	if (anchor.hasAttribute("download")) return false;
	const where = anchor.getAttribute("target");
	if (where && where !== "_self") return false;
	const ids = routesOfHref(anchor.href);
	if (!ids) return false;
	e.preventDefault();
	followRoutes(ids, isSplitClick(e));
	return true;
}

/**
 * Click handler for an anchor that navigates inside nuspace. A plain click replaces
 * the focused pane, cmd/ctrl-click opens a split. Shift and alt clicks (new
 * window, download) and the middle button are left to the browser.
 */
export function onNavClick(planeId: string) {
	return (e: React.MouseEvent<HTMLElement>) => {
		if (e.defaultPrevented || !isNavClick(e)) return;
		e.preventDefault();
		if (isSplitClick(e)) openPane(planeId);
		else replacePane(planeId);
	};
}

/**
 * Click handler for the way home (the sidebar's header): a plain click goes
 * to "/", home alone, cmd/ctrl-click opens home as a split.
 */
export function onHomeClick(e: React.MouseEvent<HTMLElement>): void {
	if (e.defaultPrevented || !isNavClick(e)) return;
	e.preventDefault();
	if (isSplitClick(e)) openPane(HOME);
	else goHome();
}

/**
 * Landing bootstrap. Anything deeper than one segment is not a route, so it
 * becomes the bare "/" (home) rather than a guess at which of its segments
 * was meant. A duplicate or empty id in the list is normalised away, and
 * "/home" is written back as "/".
 */
export function ensureLanding(): void {
	const url = hrefFor(currentRoutes());
	if (window.location.pathname === url) return;
	window.history.replaceState({}, "", url);
	emit();
}
