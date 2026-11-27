// Whether the sidebar screen is open: a fact about the history entry, not a
// flag of its own.
//
// Opening pushes a copy of the entry the tab is on, the same url with
// `SIDEBAR_STATE` set in its state. Open is "the entry carries it". So the
// browser's back closes the sidebar (and Android's back button, and the iOS
// edge swipe), forward opens it again, and nothing ever has to keep a flag in
// step with the url.
//
// Closing from inside (a swipe, the sidebar button) goes back one entry.
// Leaving through a row (`leaveThen`) goes back first and only then moves on,
// so the stack reads [plane A, plane B] and never [A, A with the sidebar, B],
// where back from B would open the sidebar again.
//
// A reload while open lands on a sidebar entry with nothing pushed under it
// in this page; the shell drops the mark in place on mount (`settleSidebar`).

import { type Entry, History, TRAVERSE_WINDOW_MS, useEntry } from "@nustackdev/ui-kit";

/** The key the sidebar's entry carries in its history state. */
export const SIDEBAR_STATE = "nuSidebar";

/** Whether `entry` is the sidebar's: open. */
export function isSidebarEntry(entry: Pick<Entry, "state">): boolean {
	const state = entry.state;
	return (
		!!state &&
		typeof state === "object" &&
		(state as Record<string, unknown>)[SIDEBAR_STATE] === true
	);
}

/** `state` with the sidebar mark, kept as it was otherwise; or without it. */
export function markState(state: unknown, on: boolean): unknown {
	const base = state && typeof state === "object" && !Array.isArray(state) ? { ...state } : {};
	const out = base as Record<string, unknown>;
	if (on) out[SIDEBAR_STATE] = true;
	else delete out[SIDEBAR_STATE];
	return Object.keys(out).length ? out : null;
}

/** Whether the sidebar is open, re-rendering as it opens and closes. */
export function useSidebarOpen(): boolean {
	return isSidebarEntry(useEntry());
}

/** Open the sidebar: the entry the tab is on, pushed again with the mark. Open: nothing. */
export function openSidebar(): void {
	const now = History.current();
	if (isSidebarEntry(now)) return;
	History.push(now.url, markState(now.state, true));
}

/** Close the sidebar: one entry back. Closed: nothing. */
export function closeSidebar(): void {
	if (isSidebarEntry(History.current())) History.back();
}

/** Open or close it. */
export function toggleSidebar(): void {
	if (isSidebarEntry(History.current())) closeSidebar();
	else openSidebar();
}

/**
 * Close the sidebar, then run `then` (a navigation) once the back has
 * landed. Closed already: `then` at once. A back whose pop never comes (it
 * should) still runs `then` once the traverse window lapses.
 */
export function leaveThen(then: () => void): void {
	if (!isSidebarEntry(History.current())) {
		then();
		return;
	}
	let done = false;
	const run = () => {
		if (done) return;
		done = true;
		unlisten();
		clearTimeout(timer);
		then();
	};
	const unlisten = History.subscribe((move) => {
		if (move.kind === "pop") run();
	});
	const timer = setTimeout(run, TRAVERSE_WINDOW_MS);
	History.back();
}

/** A page that opened on a sidebar entry (a reload while open): the mark dropped in place. */
export function settleSidebar(): void {
	const now = History.current();
	if (isSidebarEntry(now)) History.replace(now.url, markState(now.state, false));
}
