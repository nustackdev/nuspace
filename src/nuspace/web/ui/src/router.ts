// Tiny nested-path router for nuspace.
//
// Three top-level surfaces -- /pages, /apps and /lens -- each with deep paths
// (e.g. /pages/p_home/p_notes, /apps/a_ticker). We split
// window.location.pathname into (top, path[]) so the shell picks a surface and
// each surface's ref owns its own deeper navigation. Apps is single depth, so
// its path is at most one app id.
//
// Not part of the nu.ui bridge -- purely browser-side.

import type React from "react";
import { useSyncExternalStore } from "react";

export const TOPS = ["pages", "apps", "lens"] as const;
export type Top = (typeof TOPS)[number];
export const DEFAULT_TOP: Top = "pages";

export type Route = { top: Top; path: string[] };

function _split(pathname: string): Route {
	const parts = pathname.split("/").filter((s) => s.length > 0);
	const head = parts[0] ?? "";
	if ((TOPS as readonly string[]).includes(head)) {
		return { top: head as Top, path: parts.slice(1).map(decodeURIComponent) };
	}
	return { top: DEFAULT_TOP, path: [] };
}

function _join(top: Top, path: string[]): string {
	const encoded = path.map(encodeURIComponent).join("/");
	return encoded.length > 0 ? `/${top}/${encoded}` : `/${top}`;
}

/**
 * The URL a nav target resolves to. Exported so nav chrome can render real
 * anchors (kit `NavLink` is an `<a>`): middle-click, cmd-click and the status
 * bar preview all work, and the click handler only has to suppress the
 * default navigation.
 */
export function hrefFor(top: Top, path: string[] = []): string {
	return _join(top, path);
}

// Per-surface deep path, remembered across tab switches. Flipping to /lens and
// back should return you to the page you were reading, not to the root.
const lastPath: Record<string, string[]> = {};

export function rememberedPath(top: Top): string[] {
	return lastPath[top] ?? [];
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
	return _split(window.location.pathname);
}

// Cache the last route object so `useSyncExternalStore` doesn't see a
// fresh reference every render (which triggers an infinite loop).
let _cached: Route = getRoute();
let _cachedKey = _key(_cached);

function _key(r: Route): string {
	return `${r.top}::${r.path.join("/")}`;
}

function getSnapshot(): Route {
	const next = getRoute();
	const key = _key(next);
	if (key !== _cachedKey) {
		_cached = next;
		_cachedKey = key;
		lastPath[next.top] = next.path;
	}
	return _cached;
}

export function useRoute(): Route {
	return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export function navigate(target: string | { top: Top; path?: string[] }): void {
	const url = typeof target === "string" ? target : _join(target.top, target.path ?? []);
	if (window.location.pathname === url) return;
	window.history.pushState({}, "", url);
	const r = _split(url);
	lastPath[r.top] = r.path;
	for (const cb of subscribers) cb();
}

/**
 * Click handler for an anchor that navigates in-app. Modified clicks (new tab,
 * new window, download) are left to the browser -- an in-app router that eats
 * cmd+click is a worse link than a plain one.
 */
export function onNavClick(target: string | { top: Top; path?: string[] }) {
	return (e: React.MouseEvent<HTMLElement>) => {
		if (e.defaultPrevented) return;
		if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
		e.preventDefault();
		navigate(target);
	};
}

// Landing bootstrap. Bare "/" (or any unknown top) becomes /pages.
export function ensureLanding(): void {
	const p = window.location.pathname;
	const head = p.split("/").filter(Boolean)[0] ?? "";
	if (!(TOPS as readonly string[]).includes(head)) {
		window.history.replaceState({}, "", `/${DEFAULT_TOP}`);
		for (const cb of subscribers) cb();
	}
}
