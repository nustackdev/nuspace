// Tiny fixed-route router for nuspace.
//
// Nuspace has 3 known-at-compile-time top-level routes -- no dynamic
// route map, no need for a full router library. We read
// window.location.pathname, match it against the fixed set, and expose
// a hook + a navigate() that drives History pushState. `popstate` (back
// / forward) triggers a re-render via the same subscription list.
//
// Not part of the nu.ui bridge -- this router is purely browser-side
// (matches the nuspace-ui model: the shell knows its own routes; the
// server ships all pages at once and the router decides what to paint).

import { useSyncExternalStore } from "react";

export const ROUTES = ["/apps", "/pages", "/lens"] as const;
export type Route = (typeof ROUTES)[number];
export const DEFAULT_ROUTE: Route = "/lens";

function matchRoute(pathname: string): Route {
	for (const r of ROUTES) {
		if (pathname === r || pathname.startsWith(`${r}/`)) return r;
	}
	return DEFAULT_ROUTE;
}

const subscribers = new Set<() => void>();

function subscribe(cb: () => void): () => void {
	subscribers.add(cb);
	const onPop = () => cb();
	window.addEventListener("popstate", onPop);
	return () => {
		subscribers.delete(cb);
		window.removeEventListener("popstate", onPop);
	};
}

function getRoute(): Route {
	return matchRoute(window.location.pathname);
}

export function useRoute(): Route {
	return useSyncExternalStore(subscribe, getRoute, getRoute);
}

export function navigate(route: Route): void {
	if (window.location.pathname === route) return;
	window.history.pushState({}, "", route);
	// pushState does not fire popstate; wake subscribers by hand.
	for (const cb of subscribers) cb();
}

// Landing bootstrap. If the user opened `/` (or any unknown path), push
// the default route so the URL reflects what we render.
export function ensureLanding(): void {
	const p = window.location.pathname;
	if (!ROUTES.some((r) => p === r || p.startsWith(`${r}/`))) {
		window.history.replaceState({}, "", DEFAULT_ROUTE);
		for (const cb of subscribers) cb();
	}
}
