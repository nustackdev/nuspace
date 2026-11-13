// The router: what the tab shows, off the kit's History entry, the desks and
// the roles, and the ops that change them.
//
// The url names exactly what the canvas shows (the task's iteration-3.md):
//
//   /                       replaced by the home role's plane url
//   /<plane id>?<params>    solo: one plane outside any desk, its params in
//                           the query. Navigation just moves the url
//   /<desk id>/<item id>    a desk item: a plane item or a strip. Navigation
//                           inside writes that plane item's or pane's recent
//   /<desk id>              replaced by its first item's url, or the empty
//                           desk state
//
// Every segment is checked for its shape. A desk id is 8 chars [a-z0-9], an
// item id 6 (../desk/model.ts), a plane id key chars [A-Za-z0-9_-] (a minted
// `p_<hex>_<hex>_<hex>`, a system plane's name, an id given in code). A one
// segment path of a desk id's shape is a desk when the desks hold it; else it
// is a plane url when a role or a known plane has that id, and otherwise a
// desk not found. A known desk with an unknown item is an item not found. A
// plane url the server finds no plane for is the pane's own not found. Any
// other path, or a segment of no id's shape: a page not found. All of it
// waits for the desks and the roles (`pending`). Not found is never sent
// elsewhere: it stays on its url and says so (../pane/NotFound.tsx).
//
// History is the only writer of browser history. Every url move goes through
// it; back and forward step between solo planes and desk items like pages.
//
// Desks, roles and planes are inputs (`setDesks`, `setRoles`, `setPlanes`):
// this module never reads the store. A desk op writes the desk here at once,
// so the tab moves without waiting, and hands it to the write hook
// (`onDeskWrite`) that takes it to the store. The next `setDesks` is the
// store's word and wins. A closed desk goes to the delete hook
// (`onDeskDelete`). Nothing changes a desk but an explicit op or a
// navigation's recent: a click opens, never edits.
//
// Focus is per tab per strip: a plane id per desk item, in memory, never in
// the desk or the url. A click sets it. A plane item has no focus to keep:
// its one pane is it.
//
// Links are the kit's AnchorCatcher on the shell with `paneRule` below. A
// plane url decides by where the link sits: inside a pane of a desk item it
// navigates that pane in place, anywhere else (a Planes tree or nav row, a
// solo plane, the rest of the shell) it opens the plane solo. A desk or item
// url opens it. A program's push to a plane url while on a desk item reads the
// same way: the recent is written and the url goes back to the item's. A
// program's query rewrite on an item url is the focused pane's params. A Cmd
// click stays the browser's.
//
// Not part of the nustd.ui bridge: purely browser side.

import {
	type AnchorRule,
	type Entry,
	History,
	parseQuery,
	serializeQuery,
} from "@nustackdev/ui-kit";
import { useSyncExternalStore } from "react";
import type { Desk, Item, Landed, Link, Params } from "../desk/model";
import * as M from "../desk/model";

export type { Link, Params } from "../desk/model";

/** What the tab shows. */
export type Route =
	/** Before the desks and roles land, and an address on its way to landing elsewhere. */
	| { kind: "pending" }
	/** A path that is no plane, desk or item url, or "/" with no home role. */
	| { kind: "missing"; what: Missing; id: string }
	| { kind: "solo"; plane: string; params: Params }
	/** An empty desk. */
	| { kind: "desk"; desk: string; name: string }
	/** A desk item; `focus` is the focused pane's plane in a strip, the shown plane for a plane item. */
	| { kind: "item"; desk: string; name: string; item: Item; focus: string };

/** What a path names. */
export type Shape =
	| { kind: "root" }
	| { kind: "desk"; desk: string }
	| { kind: "item"; desk: string; item: string }
	| { kind: "plane"; plane: string }
	| { kind: "none" };

/** The roles the shell resolves through: role name to plane id. */
export type Roles = Record<string, string>;

/** Tags the moves this module makes, so landing can tell them from a program's. */
const ROUTER = "nuspace.router";

// -- Shapes and urls (pure) ---------------------------------------------------

/** What a not found is of: a plane, a desk, a desk's item, or a url that is none of them. */
export type Missing = "plane" | "desk" | "item" | "page";

/** A plane id's shape in a url: key chars, as the core spells keys. */
const PLANE_ID = /^[A-Za-z0-9_-]{1,128}$/;

function decode(raw: string): string | null {
	try {
		return decodeURIComponent(raw);
	} catch {
		return null;
	}
}

/**
 * What `pathname` names, given the desks known (null: not landed yet). A one
 * segment desk shaped id is a desk until the desks land, then a desk only
 * when it is one of them, else a plane.
 */
export function shapeOf(pathname: string, known: Record<string, Desk> | null = null): Shape {
	if (pathname === "/" || pathname === "") return { kind: "root" };
	const parts = pathname.split("/").slice(1).map(decode);
	if (parts.some((p) => !p)) return { kind: "none" };
	const [first, second] = parts as string[];
	if (parts.length === 2) {
		return M.isDeskId(first) && M.isItemId(second)
			? { kind: "item", desk: first, item: second }
			: { kind: "none" };
	}
	if (parts.length !== 1) return { kind: "none" };
	const desk = M.isDeskId(first) && (!known || Object.hasOwn(known, first));
	if (desk) return { kind: "desk", desk: first };
	return PLANE_ID.test(first) ? { kind: "plane", plane: first } : { kind: "none" };
}

/** A plane url: `/<plane>`, with `?<params>` when it has any. */
export function hrefFor(plane: string, params: Params = {}): string {
	const search = serializeQuery(params);
	return `/${encodeURIComponent(plane)}${search ? `?${search}` : ""}`;
}

/** A desk url. */
export function deskHref(desk: string): string {
	return `/${desk}`;
}

/** A desk item url. */
export function itemHref(desk: string, item: string): string {
	return `/${desk}/${item}`;
}

/** What an in app href points at, or null when it is no plane, desk or item url (a hash, a deeper path). */
export function shapeOfHref(
	href: string,
	known: Record<string, Desk> | null = null,
): { shape: Shape; params: Params } | null {
	let url: URL;
	try {
		url = new URL(href, "http://nuspace.invalid/");
	} catch {
		return null;
	}
	if (url.hash) return null;
	const shape = shapeOf(url.pathname, known);
	return shape.kind === "none" ? null : { shape, params: parseQuery(url.search) };
}

/**
 * For a desk shaped id that is no desk: true when a role or a known plane has
 * it, false when neither does (a desk not found), null while the planes have
 * not landed.
 */
export function isKnownPlane(
	id: string,
	roles: Roles | null,
	planes: ReadonlySet<string> | null,
): boolean | null {
	if (roles && Object.values(roles).includes(id)) return true;
	return planes ? planes.has(id) : null;
}

/** The plane to focus in `item`: `focus` while the item shows it, else its first. */
function settle(item: Item, focus: string): string {
	const shown = M.shownLinks(item).map((l) => l.plane);
	return shown.includes(focus) ? focus : shown[0];
}

function itemRoute(desk: string, d: Desk, item: Item, focus: string): Route {
	return { kind: "item", desk, name: d.name, item, focus: settle(item, focus) };
}

/**
 * The route of an entry, given the desks, roles and planes known (null: not
 * landed yet). Focus is the first pane's: the router keeps each tab's own.
 */
export function resolve(
	entry: Pick<Entry, "path" | "query">,
	desks: Record<string, Desk> | null,
	roles: Roles | null,
	planes: ReadonlySet<string> | null = null,
): Route {
	if (!desks || !roles) return { kind: "pending" };
	const shape = shapeOf(entry.path, desks);
	switch (shape.kind) {
		case "root":
			return roles.home
				? { kind: "solo", plane: roles.home, params: {} }
				: { kind: "missing", what: "page", id: "/" };
		case "plane":
			if (M.isDeskId(shape.plane)) {
				// A desk's shape and no desk: a plane by that id, or a desk not found.
				const known = isKnownPlane(shape.plane, roles, planes);
				if (known === null) return { kind: "pending" };
				if (!known) return { kind: "missing", what: "desk", id: shape.plane };
			}
			return { kind: "solo", plane: shape.plane, params: { ...entry.query } };
		case "desk": {
			const d = desks[shape.desk];
			const first = d.items[0];
			return first
				? itemRoute(shape.desk, d, first, "")
				: { kind: "desk", desk: shape.desk, name: d.name };
		}
		case "item": {
			const d = desks[shape.desk];
			if (!d) return { kind: "missing", what: "desk", id: shape.desk };
			const item = M.itemOf(d, shape.item);
			return item
				? itemRoute(shape.desk, d, item, "")
				: { kind: "missing", what: "item", id: `${d.name} / ${shape.item}` };
		}
		default:
			return { kind: "missing", what: "page", id: entry.path };
	}
}

// -- Inputs -------------------------------------------------------------------

let desks: Record<string, Desk> | null = null;
let roles: Roles | null = null;
/** The planes that exist. Null until fed. */
let planeIds: ReadonlySet<string> | null = null;
const writers = new Set<(id: string, desk: Desk) => void>();
const deleters = new Set<(id: string) => void>();
/** The focused plane per strip (`<desk>/<item>`), this tab only. */
const focusOf = new Map<string, string>();
/** Bumped on every input change, so a read knows to rebuild. */
let version = 0;

/** A program's push onto a plane url, read as navigation inside the item it left: shown as that item until landing puts its url back. */
let held: { entry: Entry; desk: string; item: string } | null = null;

const key = (desk: string, item: string) => `${desk}/${item}`;

/** This tab's focus in `item` of desk `desk`, settled. */
function focusIn(desk: string, item: Item): string {
	return settle(item, focusOf.get(key(desk, item.id)) ?? "");
}

/** The desks the store holds, by id. Null until they land. */
export function setDesks(next: Record<string, Desk> | null): void {
	const was = desks;
	desks = next;
	follow(was);
	changed();
}

/**
 * What this tab shows, gone under it (closed here or in another tab): the
 * desk gone, the tab goes home; the item gone, to the desk, which lands on
 * its first item. Only what was there before: a url landed on that never was
 * a desk or an item stays and says not found.
 */
function follow(was: Record<string, Desk> | null): void {
	if (!was || !desks) return;
	const shape = shapeOf(History.current().path, was);
	if (shape.kind !== "desk" && shape.kind !== "item") return;
	if (!Object.hasOwn(was, shape.desk)) return;
	if (!Object.hasOwn(desks, shape.desk)) {
		go(homeHref(), "replace");
		return;
	}
	const gone =
		shape.kind === "item" &&
		M.itemOf(was[shape.desk], shape.item) &&
		!M.itemOf(desks[shape.desk], shape.item);
	if (gone) go(deskHref(shape.desk), "replace");
}

/** The roles the store holds. Null until they land. */
export function setRoles(next: Roles | null): void {
	roles = next;
	changed();
}

/** The plane ids that exist, from the plane list. Null (the default): not known yet. */
export function setPlanes(ids: Iterable<string> | null): void {
	planeIds = ids ? new Set(ids) : null;
	changed();
}

/** Hear every desk this tab writes, to take it to the store. Returns the unsubscribe. */
export function onDeskWrite(fn: (id: string, desk: Desk) => void): () => void {
	writers.add(fn);
	return () => writers.delete(fn);
}

/** Hear every desk this tab closes. Returns the unsubscribe. */
export function onDeskDelete(fn: (id: string) => void): () => void {
	deleters.add(fn);
	return () => deleters.delete(fn);
}

/** The desks known now, null before they land. */
export function knownDesks(): Record<string, Desk> | null {
	return desks;
}

// -- Reading ------------------------------------------------------------------

let read: { entry: Entry; version: number; route: Route; routes: string[] } | null = null;

function routeNow(entry: Entry): Route {
	const hold = held?.entry === entry && desks?.[held.desk];
	const kept = hold && held ? M.itemOf(hold, held.item) : null;
	if (hold && held && kept) return itemRoute(held.desk, hold, kept, focusIn(held.desk, kept));
	const route = resolve(entry, desks, roles, planeIds);
	if (route.kind !== "item" || !desks) return route;
	return { ...route, focus: focusIn(route.desk, route.item) };
}

function routesOf(route: Route): string[] {
	if (route.kind === "solo") return [route.plane];
	if (route.kind === "item") return M.shownLinks(route.item).map((l) => l.plane);
	return [];
}

function snapshot() {
	const entry = History.current();
	if (read?.entry === entry && read.version === version) return read;
	const route = routeNow(entry);
	const planes = routesOf(route);
	const routes =
		read && read.routes.length === planes.length && read.routes.every((id, i) => id === planes[i])
			? read.routes
			: planes;
	const same = read && JSON.stringify(read.route) === JSON.stringify(route);
	read = { entry, version, route: same && read ? read.route : route, routes };
	return read;
}

/** What the tab shows now. Callable outside a render. */
export function currentRoute(): Route {
	return snapshot().route;
}

/** The planes the canvas shows, in order: what `planes.open` reports. Callable outside a render. */
export function currentRoutes(): string[] {
	return snapshot().routes;
}

/** The focused plane: the solo plane, a plane item's shown plane, a strip's focused pane. "" with none. */
export function focusedRoute(): string {
	const route = currentRoute();
	return route.kind === "item" ? route.focus : route.kind === "solo" ? route.plane : "";
}

/** The params `plane` is shown with now, {} when it is not shown. */
export function paramsOf(plane: string): Params {
	const route = currentRoute();
	if (route.kind === "solo") return route.plane === plane ? route.params : {};
	if (route.kind === "item") {
		return M.shownLinks(route.item).find((l) => l.plane === plane)?.params ?? {};
	}
	return {};
}

/** The name of the desk the tab is on, "" for a solo plane. The tab title is the shown plane's title plus this. */
export function deskName(): string {
	const route = currentRoute();
	return route.kind === "item" || route.kind === "desk" ? route.name : "";
}

// One History subscription for the whole router, fanned out to every reader,
// landing included. Held while anyone listens.
const readers = new Set<() => void>();
let unlisten: (() => void) | null = null;

function emit(): void {
	for (const fn of [...readers]) fn();
}

function changed(): void {
	version++;
	emit();
}

function subscribe(cb: () => void): () => void {
	readers.add(cb);
	unlisten ??= History.subscribe((move) => {
		lay(move);
		emit();
	});
	return () => {
		readers.delete(cb);
		if (readers.size === 0 && unlisten) {
			unlisten();
			unlisten = null;
		}
	};
}

/** What the tab shows, re-rendering on every change. */
export function useRoute(): Route {
	return useSyncExternalStore(subscribe, currentRoute, currentRoute);
}

/** The planes the canvas shows, in order. */
export function useRoutes(): string[] {
	return useSyncExternalStore(subscribe, currentRoutes, currentRoutes);
}

/** The focused plane, or "" when nothing is shown. */
export function useFocusedRoute(): string {
	return useSyncExternalStore(subscribe, focusedRoute, focusedRoute);
}

// -- Writing ------------------------------------------------------------------

function go(url: string, kind: "push" | "replace" = "push"): void {
	History[kind](url, null, { origin: ROUTER });
}

/** Home's plane url once the roles are known, else "/" (which lands there). */
/** The home role's plane url, "/" while the roles are unknown. */
export function homeHref(): string {
	return roles?.home ? hrefFor(roles.home) : "/";
}

/** Write a desk: here at once, then to the store. The same desk: nothing. */
function writeDesk(id: string, desk: Desk): void {
	if (desks?.[id] === desk) return;
	const was = desks;
	desks = { ...(desks ?? {}), [id]: desk };
	follow(was);
	changed();
	for (const fn of [...writers]) fn(id, desk);
}

/** Apply a move to desk `id`. Unknown desk, or a move that changes nothing: no write. */
function deskMove(id: string, move: (desk: Desk) => Desk): void {
	const desk = desks?.[id];
	if (desk) writeDesk(id, move(desk));
}

/** Write several desks at once: one drag that moves something between desks. */
export function writeDesks(changes: Record<string, Desk>): void {
	for (const [id, desk] of Object.entries(changes)) writeDesk(id, desk);
}

/** Whether the tab shows desk `desk` (its item `item`, when given). */
function isOn(desk: string, item?: string): boolean {
	const route = currentRoute();
	if (route.kind === "desk") return route.desk === desk && item === undefined;
	return (
		route.kind === "item" && route.desk === desk && (item === undefined || route.item.id === item)
	);
}

// A pane asked for while it is already shown (a sidebar click, a dedupe) takes
// focus and should come on screen. The canvas listens here.
const revealers = new Set<(planeId: string) => void>();

/** Listen for a shown pane being asked for again. Returns the unsubscribe. */
export function onReveal(fn: (planeId: string) => void): () => void {
	revealers.add(fn);
	return () => revealers.delete(fn);
}

function reveal(planeId: string): void {
	for (const fn of revealers) fn(planeId);
}

/** Focus `plane` in strip `item` of desk `desk`: kept per tab, never written. */
function setFocus(desk: string, item: string, plane: string): void {
	if (!plane || focusOf.get(key(desk, item)) === plane) return;
	focusOf.set(key(desk, item), plane);
	changed();
}

/**
 * A move that lands on a pane: the desk written, the pane focused, and in a
 * strip the tab shows, brought on screen (a dedupe focuses another pane).
 */
function landOn(desk: string, item: string, landed: Landed): void {
	writeDesk(desk, landed.desk);
	if (!landed.focus || !desks?.[desk] || !M.stripOf(desks[desk], item)) return;
	setFocus(desk, item, landed.focus);
	if (isOn(desk, item)) reveal(landed.focus);
}

// -- Opening and navigating -----------------------------------------------------

/** Open a plane solo, outside any desk: a Planes tree or nav row, a link in a solo plane. Pushed. */
export function openPlane(to: string | Link): void {
	const link = typeof to === "string" ? { plane: to, params: {} } : to;
	if (link.plane) go(hrefFor(link.plane, link.params));
}

/** Open desk item `item` (a desk item row). Already on it: nothing. */
export function openItem(desk: string, item: string): void {
	if (!isOn(desk, item)) go(itemHref(desk, item));
}

/** Open desk `desk`: its first item, or the empty desk when it has none. */
export function openDesk(desk: string): void {
	const first = desks?.[desk]?.items[0];
	if (first) openItem(desk, first.id);
	else if (!isOn(desk)) go(deskHref(desk));
}

/** Open the strip `item` with the pane showing `plane` focused and brought on screen (a pane row). */
export function openPane(desk: string, item: string, plane: string): void {
	const strip = desks?.[desk] && M.stripOf(desks[desk], item);
	if (strip && M.locate(strip, plane)) focusOf.set(key(desk, item), plane);
	if (isOn(desk, item)) changed();
	else go(itemHref(desk, item));
	reveal(plane);
}

/**
 * A link followed inside what the tab shows: on a desk item it navigates the
 * plane item, or the pane showing `pane` (the focused one when not given), in
 * place and writes its recent; anywhere else it opens the plane solo.
 */
export function navigate(link: Link, pane = ""): void {
	if (!link.plane) return;
	const route = currentRoute();
	if (route.kind !== "item") {
		openPlane(link);
		return;
	}
	const from = route.item.kind === "strip" ? pane || route.focus : "";
	const landed = M.navigate(desks?.[route.desk] as Desk, route.item.id, link, from);
	landOn(route.desk, route.item.id, landed);
}

/** Focus the pane showing `plane` in strip `item` of desk `desk` (a click). No write. */
export function focusPane(desk: string, item: string, plane: string): void {
	const strip = desks?.[desk] && M.stripOf(desks[desk], item);
	if (strip && M.locate(strip, plane)) setFocus(desk, item, plane);
}

/** Open a plane in a new browser tab, solo, with the params it is shown with. */
export function openInNewTab(planeId: string): void {
	window.open(hrefFor(planeId, paramsOf(planeId)), "_blank", "noopener");
}

/**
 * Planes gone (removed): a tab showing one of them solo goes home, pushed, or
 * as a replace for a plane back should not bring back. A desk item drops them
 * through the desks feed (the server prunes).
 */
export function leavePlanes(planeIds: string[], replace = false): void {
	const route = currentRoute();
	if (route.kind === "solo" && planeIds.includes(route.plane))
		go(homeHref(), replace ? "replace" : "push");
}

// -- Desk ops by id -------------------------------------------------------------

/** A new empty desk named "Untitled", written. Its id. */
export function createDesk(): string {
	const id = M.mintDeskId((x) => !!desks?.[x]);
	writeDesk(id, { name: M.NEW_DESK_NAME, items: [] });
	return id;
}

/** Rename desk `id`. */
export function renameDesk(id: string, name: string): void {
	deskMove(id, (d) => M.rename(d, name));
}

/** Leave the desk the tab is on, keeping it: to "/", which lands on home. Pushed. */
export function leaveDesk(): void {
	go("/");
}

/** Close desk `id`: gone here at once, then from the store. A tab showing it goes home. */
export function closeDesk(id: string): void {
	if (!desks || !Object.hasOwn(desks, id)) return;
	const on = isOn(id);
	const { [id]: _, ...rest } = desks;
	desks = rest;
	for (const k of [...focusOf.keys()]) if (k.startsWith(`${id}/`)) focusOf.delete(k);
	if (on) go(homeHref(), "replace");
	changed();
	for (const fn of [...deleters]) fn(id);
}

/** Save the plane item `item`, or its pane showing `plane`: its recent becomes its original. */
export function saveItem(desk: string, item: string, plane = ""): void {
	deskMove(desk, (d) => M.save(d, item, plane));
}

/**
 * Reset the plane item `item`, or its pane showing `plane`, to the original.
 * In a strip, an original another pane shows focuses that pane instead.
 */
export function resetItem(desk: string, item: string, plane = ""): void {
	const d = desks?.[desk];
	if (d) landOn(desk, item, M.reset(d, item, plane));
}

/** Close item `item` of desk `desk`. */
export function closeItem(desk: string, item: string): void {
	deskMove(desk, (d) => M.closeItem(d, item));
}

/** Close the pane showing `plane` in strip `item` (one pane left: the strip becomes a plane item). */
export function closePane(desk: string, item: string, plane: string): void {
	deskMove(desk, (d) => M.closePane(d, item, plane));
}

/** Close the column at index `column` of strip `item`. */
export function closeColumn(desk: string, item: string, column: number): void {
	deskMove(desk, (d) => M.closeColumn(d, item, column));
}

/** The width, px, of the column of strip `item` holding `plane`. */
export function setWidth(desk: string, item: string, plane: string, width: number): void {
	deskMove(desk, (d) => M.setWidth(d, item, plane, width));
}

/** The pane shares of the column of strip `item` holding `plane`, top to bottom. */
export function setShares(desk: string, item: string, plane: string, shares: number[]): void {
	deskMove(desk, (d) => M.setShares(d, item, plane, shares));
}

/**
 * The gesture rule for in app links, the AnchorCatcher's on the shell. A
 * plane url (or "/", home's) decides by where the anchor sits: inside a pane
 * (`[data-pane]`) of the desk item the tab shows, it navigates that pane in
 * place; anywhere else it opens the plane solo. A desk or item url opens it.
 * False, so native, for anything else. Option is no gesture of its own: it
 * reads as a plain click.
 */
export const paneRule: AnchorRule = (href, _gesture, anchor) => {
	const hit = shapeOfHref(href, desks);
	if (!hit) return false;
	const { shape, params } = hit;
	if (shape.kind === "desk") go(deskHref(shape.desk));
	else if (shape.kind === "item") openItem(shape.desk, shape.item);
	else {
		const plane = shape.kind === "root" ? roles?.home : shape.kind === "plane" ? shape.plane : "";
		const link = { plane: plane ?? "", params: shape.kind === "root" ? {} : params };
		const pane = anchor?.closest?.("[data-pane]")?.getAttribute("data-pane") ?? "";
		if (!link.plane) go("/");
		else if (pane) navigate(link, pane);
		else openPlane(link);
	}
	return true;
};

// -- Landing -------------------------------------------------------------------

/**
 * A program's move, heard as it lands, while the tab was on a desk item: a
 * push to a plane url navigates that item's focused pane (or the plane item)
 * and is held as that item until landing puts the item url back; a query on
 * the item url is the focused pane's params.
 */
function lay(move: { kind: string; origin: unknown; entry: Entry; previous: Entry }): void {
	if (move.kind === "pop" || move.origin === ROUTER || !desks || !roles) return;
	const before = resolve(move.previous, desks, roles, planeIds);
	if (before.kind !== "item") return;
	const { entry } = move;
	const { desk, item } = before;
	const shape = shapeOf(entry.path, desks);
	const focus = focusIn(desk, item);
	let link: Link | null = null;
	if (shape.kind === "plane") {
		link = { plane: shape.plane, params: { ...entry.query } };
		held = { entry, desk, item: item.id };
	} else if (shape.kind === "item" && shape.desk === desk && shape.item === item.id) {
		if (Object.keys(entry.query).length) link = { plane: focus, params: { ...entry.query } };
	}
	if (!link) return;
	const landed = M.navigate(desks[desk], item.id, link, item.kind === "strip" ? focus : "");
	writeDesk(desk, landed.desk);
	if (landed.focus) focusOf.set(key(desk, item.id), landed.focus);
}

/**
 * Every entry the page lands on, made right in place, once the desks and the
 * roles are known: "/" as home's plane url, a held program push as its item
 * url, `/<desk id>` as its first item's url, and a query or hash on a desk or
 * item url dropped. All replaces. What is not found (an unknown desk or item,
 * a desk shaped id that is no plane either) stays on its url and draws the
 * not found pane (`resolve`).
 */
function land(): void {
	if (!desks || !roles) return;
	const entry = History.current();
	if (held) {
		const { desk, item } = held;
		const on = held.entry === entry;
		held = null;
		if (on) {
			go(itemHref(desk, item), "replace");
			return;
		}
	}
	const shape = shapeOf(entry.path, desks);
	const bare = entry.url === entry.path && !entry.hash;
	if (shape.kind === "root") {
		if (roles.home) go(hrefFor(roles.home), "replace");
	} else if (shape.kind === "desk") {
		const first = desks[shape.desk].items[0];
		if (first) go(itemHref(shape.desk, first.id), "replace");
		else if (!bare) go(deskHref(shape.desk), "replace");
	} else if (shape.kind === "item") {
		const d = desks[shape.desk];
		if (d && M.itemOf(d, shape.item) && !bare) go(itemHref(shape.desk, shape.item), "replace");
	}
}

let landing = false;

/**
 * Landing bootstrap: the entry the tab opened on, and every entry after it,
 * and again whenever the desks, roles or planes change (so "/" lands once the
 * roles do). For the tab's whole life; after the move that landed has been
 * heard.
 */
export function ensureLanding(): void {
	land();
	if (landing) return;
	landing = true;
	subscribe(() => queueMicrotask(land));
}

/** Forget every input and the tab's memory. Tests only. */
export function resetRouter(): void {
	desks = null;
	roles = null;
	planeIds = null;
	held = null;
	writers.clear();
	deleters.clear();
	focusOf.clear();
	changed();
}
