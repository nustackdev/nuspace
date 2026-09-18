// The router. A route is which Plane is open, and nothing else.
//
// One segment: /<plane id>. Bare "/" is a legal route and means nothing is
// open, which is what a tab lands on before anybody picks a row. There is no
// top-level surface to pick any more and no deep path under one, because the
// sidebar is the only thing that navigates and a Plane is one row at a fixed
// depth however it is grouped.
//
// Not part of the nustd.ui bridge -- purely browser-side.

import type React from "react";
import { useSyncExternalStore } from "react";

/** The plane id in `pathname`, or "" when it names none. */
function _split(pathname: string): string {
	const parts = pathname.split("/").filter((s) => s.length > 0);
	return parts.length === 1 ? decodeURIComponent(parts[0]) : "";
}

/**
 * The URL a Plane resolves to. Exported so the sidebar can render real anchors
 * (kit `NavLink` is an `<a>`): middle-click, cmd-click and the status bar
 * preview all work, and the click handler only has to suppress the default
 * navigation.
 */
export function hrefFor(planeId: string): string {
	return planeId ? `/${encodeURIComponent(planeId)}` : "/";
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

function getSnapshot(): string {
	return _split(window.location.pathname);
}

/** The Plane this tab has open, or "" when it has none. */
export function useRoute(): string {
	return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export function navigate(planeId: string): void {
	const url = hrefFor(planeId);
	if (window.location.pathname === url) return;
	window.history.pushState({}, "", url);
	for (const cb of subscribers) cb();
}

/**
 * Click handler for an anchor that navigates in-app. Modified clicks (new tab,
 * new window, download) are left to the browser -- an in-app router that eats
 * cmd+click is a worse link than a plain one.
 */
export function onNavClick(planeId: string) {
	return (e: React.MouseEvent<HTMLElement>) => {
		if (e.defaultPrevented) return;
		if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
		e.preventDefault();
		navigate(planeId);
	};
}

/**
 * Landing bootstrap. Anything deeper than one segment is not a route, so it
 * becomes the bare "/" rather than a guess at which of its segments was meant.
 */
export function ensureLanding(): void {
	const parts = window.location.pathname.split("/").filter(Boolean);
	if (parts.length <= 1) return;
	window.history.replaceState({}, "", "/");
	for (const cb of subscribers) cb();
}
