// The pane router: the desk's layout off the kit's History entry, and the
// moves that change it.
//
// The layout and its URL are ./layout.ts: the entry's state is the layout
// `{panes: [{plane, params}], focus}`, the URL is the focused pane
// (`/movie?id=42`), and an entry with no layout is one pane off its URL.
// History is the only writer of browser history. This module listens to it,
// once, and every move here is a pure layout move written back through it:
//
//   a link followed, a sidebar click   push    openHere
//   Option on a link or a row          push    openBeside
//   a drop on the desk                 push    openAt
//   close, drag or reorder a pane      push    close / move (back undoes it)
//   focus another pane                 replace focus (the URL follows it)
//
// Anyone else's push or replace (a program's `HistoryRef.push`, a link the
// kit pushes by default) carries no layout. The desk reads it as a place
// opened in the focused pane, every other pane kept, and landing writes that
// layout into the entry so back and reload bring it back. Nobody but the user closes
// a pane; a program says where and never touches the desk.
//
// Back, forward and reload are the browser's: the entry comes back with its
// state, and everything that reads the layout redraws. Nothing here keeps a
// copy of it. Telling the server what is open is the viewer's
// (../main/Main.tsx), one way, off the same reads.
//
// Links are the kit's AnchorCatcher on the shell with `paneRule` below: a
// plain click or Enter opens in the focused pane, Option opens beside, and
// anything that is not a pane URL (a deeper path, a hash) is left native.
//
// "/" is home: it reads as the home pane, and `ensureLanding` replaces it
// with /home, at boot and whenever an entry lands on it.
//
// Not part of the nustd.ui bridge -- purely browser-side.

import { type AnchorRule, type Entry, History, type Move } from "@nustackdev/ui-kit";
import { useSyncExternalStore } from "react";
import type { Layout, Params, Target } from "./layout";
import * as L from "./layout";

export type { Layout, PaneEntry, Params, Target } from "./layout";
export { HOME, layoutOf, targetOfHref, urlOf } from "./layout";

// -- Reading -----------------------------------------------------------------

// The layout of the entry the page is on, rebuilt only when the entry is a new
// one. The plane list keeps its identity while the planes stay the same, so a
// focus move or a params change re-renders nothing that only lists them.
let read: { entry: Entry; layout: Layout; routes: string[] } | null = null;

function snapshot() {
	const entry = History.current();
	if (read?.entry === entry) return read;
	const layout = laid.get(entry) ?? L.layoutOf(entry);
	const planes = L.planesOf(layout);
	const routes =
		read && read.routes.length === planes.length && read.routes.every((id, i) => id === planes[i])
			? read.routes
			: planes;
	read = { entry, layout, routes };
	return read;
}

/**
 * The layouts of entries pushed without one (a program's `HistoryRef.push`):
 * the place opened in the focused pane of the desk the move left, every
 * other pane kept. Worked out as the move is heard, so no reader ever sees
 * the desk without its other panes; landing (`ensureLanding`) then writes it
 * into the entry.
 */
const laid = new WeakMap<Entry, Layout>();

function lay(move: Move): void {
	const { entry, previous } = move;
	if (move.kind === "pop" || L.stateLayout(entry.state) !== null) return;
	const plane = L.planeOfPath(entry.path);
	if (!plane) return;
	const was = laid.get(previous) ?? L.layoutOf(previous);
	laid.set(entry, L.openHere(was, { plane, params: { ...entry.query } }));
}

/** The desk's layout now. Callable outside a render. */
export function currentLayout(): Layout {
	return snapshot().layout;
}

/** The Planes open, left to right. Callable outside a render. */
export function currentRoutes(): string[] {
	return snapshot().routes;
}

/** The focused pane's Plane, "" with none. Callable outside a render. */
export function focusedRoute(): string {
	const layout = currentLayout();
	return layout.panes[layout.focus]?.plane ?? "";
}

/** The params of the pane showing `plane`, {} when it is not open. */
export function paramsOf(plane: string): Params {
	return currentLayout().panes.find((p) => p.plane === plane)?.params ?? {};
}

// One History subscription for the whole router, fanned out to every reader,
// landing included (see `ensureLanding`). Held while anyone listens.
const readers = new Set<() => void>();
let unlisten: (() => void) | null = null;

function subscribe(cb: () => void): () => void {
	readers.add(cb);
	unlisten ??= History.subscribe((move) => {
		lay(move);
		for (const fn of [...readers]) fn();
	});
	return () => {
		readers.delete(cb);
		if (readers.size === 0 && unlisten) {
			unlisten();
			unlisten = null;
		}
	};
}

/** The desk's layout, re-rendering on every move that changes it. */
export function useLayout(): Layout {
	return useSyncExternalStore(subscribe, currentLayout, currentLayout);
}

/** The Planes open, left to right. */
export function useRoutes(): string[] {
	return useSyncExternalStore(subscribe, currentRoutes, currentRoutes);
}

/** The focused pane's Plane, or "" when nothing is open. */
export function useFocusedRoute(): string {
	return useSyncExternalStore(subscribe, focusedRoute, focusedRoute);
}

/** A pane's URL, for a real anchor: `/<plane>`, or `/<plane>?<params>`. */
export function hrefFor(plane: string, params: Params = {}): string {
	return L.hrefOf({ plane, params });
}

// -- Moving ------------------------------------------------------------------

/**
 * Write `next` through History: its focused pane's URL, the layout as state.
 * The layout the page already shows is no move, even on an entry that has no
 * state yet (a copied link), so it never adds an entry nothing changed in.
 */
function commit(next: Layout, kind: "push" | "replace" = "push"): void {
	if (JSON.stringify(next) === JSON.stringify(currentLayout())) return;
	History[kind](L.urlOf(next), next);
}

// A pane asked for while it is already open (a sidebar click, "Open on desk",
// a drop) takes focus and should come on screen. The planes may not change, so
// nothing re-renders to notice: the desk listens here instead.
const revealers = new Set<(planeId: string) => void>();

/** Listen for an open pane being asked for again. Returns the unsubscribe. */
export function onReveal(fn: (planeId: string) => void): () => void {
	revealers.add(fn);
	return () => revealers.delete(fn);
}

function reveal(planeId: string): void {
	for (const fn of revealers) fn(planeId);
}

function targetOf(to: string | Target): Target {
	return typeof to === "string" ? { plane: to, params: {} } : to;
}

/** One open move: written, and the pane revealed if it was open already. */
function opening(to: string | Target, move: (layout: Layout, target: Target) => Layout): void {
	const target = targetOf(to);
	if (!target.plane) return;
	const layout = currentLayout();
	const was = L.indexOf(layout, target.plane) >= 0;
	commit(move(layout, target));
	if (was) reveal(target.plane);
}

/** Open in the focused pane: a link, a sidebar click. A Plane id is that Plane with no params. */
export function openHere(to: string | Target): void {
	opening(to, L.openHere);
}

/** Open beside the focused pane, focused: Option on a link or a row, "Open on desk". */
export function openBeside(to: string | Target): void {
	opening(to, L.openBeside);
}

/** Open as a new pane at `index` (the end when out of range): a drop on the desk. */
export function openAt(planeId: string, index: number): void {
	opening(planeId, (layout, target) => L.openAt(layout, target, index));
}

/**
 * Close the panes showing any of `planeIds`. `replace` rewrites the entry
 * instead of pushing one, for a Plane that no longer exists and that the back
 * button should not bring back.
 */
export function closePanes(planeIds: string[], replace = false): void {
	const layout = currentLayout();
	const next = L.close(layout, planeIds);
	if (next !== layout) commit(next, replace ? "replace" : "push");
}

/** Close one pane. */
export function closePane(planeId: string): void {
	closePanes([planeId]);
}

/** Move the pane showing `planeId` to `index` among the others, focused. */
export function movePane(planeId: string, index: number): void {
	commit(L.move(currentLayout(), planeId, index));
}

/** Focus the pane showing `planeId`. A replace: focus is not a place, the URL just follows it. */
export function focusPane(planeId: string): void {
	const layout = currentLayout();
	const next = L.focus(layout, L.indexOf(layout, planeId));
	if (next !== layout) commit(next, "replace");
}

/** Open a Plane in a new browser tab, on its own URL, with the params its pane has. */
export function openInNewTab(planeId: string): void {
	window.open(hrefFor(planeId, paramsOf(planeId)), "_blank", "noopener");
}

/**
 * The gesture rule for in-app links, the AnchorCatcher's on the shell: plain
 * opens in the focused pane, Option opens beside. False, so native, for
 * anything that is not a pane URL.
 */
export const paneRule: AnchorRule = (href, gesture) => {
	const target = L.targetOfHref(href);
	if (!target) return false;
	if (gesture === "alt") openBeside(target);
	else openHere(target);
	return true;
};

// -- Landing -----------------------------------------------------------------

/**
 * Every entry the page lands on gets its layout written in, in place: "/" and
 * anything else that names no Plane as /home, the tab's first entry as the
 * one pane it names, and a push the desk did not make (a program's) as the
 * place opened in the focused pane, the other panes kept. So back and reload
 * always find a layout.
 */
function land(): void {
	const entry = History.current();
	if (L.planeOfPath(entry.path) !== null && L.stateLayout(entry.state) !== null) return;
	const layout = currentLayout();
	History.replace(L.urlOf(layout), layout);
}

let landing = false;

/**
 * Landing bootstrap: the URL the tab opened on, made a pane URL, and the same
 * for every entry after it that names no Plane (a program pushing "/"). A
 * reader on the router's one subscription, for the tab's whole life; after the
 * move that landed there has been heard, not inside it.
 */
export function ensureLanding(): void {
	land();
	if (landing) return;
	landing = true;
	subscribe(() => queueMicrotask(land));
}
