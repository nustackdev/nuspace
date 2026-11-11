// The browser side of desks and roles (the task's contract.md).
//
// In: the `DesksRef` node (../refs/desks.ts) ships `set_desks` (every desk,
// whole, and `order`: the desk ids in creation order, Favorites first),
// `set_roles` (home, settings, search) and `set_titles` (the title
// and icon of every plane any desk item or pane holds, original and
// recent). Each write replaces what this tab had.
// Desks and roles go on to the router (`setDesks`, `setRoles`), which is
// what the tab shows; titles stay here, for a pane this tab neither has open
// nor sees in its lazy tree (`useDeskTitles`, read by ./looks.ts). The shipped desk is the truth, this tab's own echo
// included: last write wins.
//
// Out: a desk move in the router writes the desk here at once and hands it
// to `onDeskWrite`, which lands in `push` below: `desk.create` for a desk the
// server does not have yet, `desk.set` otherwise. A create is "pending" until
// a `set_desks` carries its id, so a second move before the echo is a set,
// not a second create, and the desk stays on screen while it waits. A desk
// the router closes comes through `onDeskDelete` and goes out as
// `desk.delete`.
//
// Desks are read in the items shape only (plane items and strips, each with
// its original and recent links): a desk stored in an older shape (`strips`,
// top level `columns`) is skipped on read.
//
// The ops go through the node's own path, taken from the write that fed it
// (the node is found by type, like the other regions). Nothing is sent
// before the first feed: there is no desk to write before then.

import type { Path } from "@nustackdev/ui-core";
import { useSyncExternalStore } from "react";
import type { Desk } from "../desk/model";
import { readDesk } from "../desk/model";
import { onDeskDelete, onDeskWrite, setDesks, setRoles } from "./router";
import { notifyOp } from "./wire";

/** The roles the shell resolves through. */
export const ROLES = ["home", "settings", "search"] as const;
export type Role = (typeof ROLES)[number];
export type Roles = Record<Role, string>;

/** The ops on the `DesksRef` node, by name, with their payloads. */
export type DeskOps = {
	"desk.create": { desk_id: string; desk: Desk };
	"desk.set": { desk_id: string; desk: Desk };
	"desk.delete": { desk_id: string };
	"desk.move": { desk_id: string; before: string };
	"role.set": { role: Role; plane_id: string };
};

let at: Path | null = null;
/** The last `set_desks`, as shipped. Null until it lands. */
let shipped: Record<string, Desk> | null = null;
/** Desks this tab created that no `set_desks` has carried yet. */
const pending = new Map<string, Desk>();
/** What the tab knows: shipped, plus pending creates, plus its own writes since. */
let desks: Record<string, Desk> | null = null;
let roles: Roles | null = null;
/** The last shipped `order`: desk ids in creation order. */
let order: string[] = [];
/** The desk ids to draw: `order` first, then any desk it misses (a create before its echo). */
let ids: string[] = [];

function reorder(): void {
	const known = desks ?? {};
	const next = order.filter((id) => Object.hasOwn(known, id));
	for (const id of Object.keys(known)) if (!next.includes(id)) next.push(id);
	if (next.length !== ids.length || next.some((id, i) => id !== ids[i])) ids = next;
}

/** A plane's title and icon, as `set_titles` ships them. `""` for none. */
export type PlaneLook = { title: string; icon: string };
const NO_TITLES: Record<string, PlaneLook> = {};
/** The last `set_titles`: plane id to its look. Empty until it lands. */
let titles: Record<string, PlaneLook> = NO_TITLES;

const readers = new Set<() => void>();

function emit(): void {
	for (const fn of [...readers]) fn();
}

function subscribe(cb: () => void): () => void {
	readers.add(cb);
	return () => readers.delete(cb);
}

function send<K extends keyof DeskOps & string>(op: K, args: DeskOps[K]): void {
	if (at) notifyOp<DeskOps, K>(at, op, args);
}

/** A desk this tab wrote, on its way to the store. */
function push(id: string, desk: Desk): void {
	const known = !!shipped?.[id] || pending.has(id);
	if (!known || pending.has(id)) pending.set(id, desk);
	desks = { ...(desks ?? {}), [id]: desk };
	reorder();
	emit();
	send(known ? "desk.set" : "desk.create", { desk_id: id, desk });
}

function readDesks(raw: unknown): Record<string, Desk> {
	const out: Record<string, Desk> = {};
	if (!raw || typeof raw !== "object" || Array.isArray(raw)) return out;
	for (const [id, value] of Object.entries(raw)) {
		const desk = readDesk(value);
		if (desk) out[id] = desk;
	}
	return out;
}

function readTitles(raw: unknown): Record<string, PlaneLook> {
	const out: Record<string, PlaneLook> = {};
	if (!raw || typeof raw !== "object" || Array.isArray(raw)) return out;
	for (const [id, value] of Object.entries(raw)) {
		if (!value || typeof value !== "object") continue;
		const v = value as Record<string, unknown>;
		const text = (x: unknown) => (typeof x === "string" ? x : "");
		out[id] = { title: text(v.title), icon: text(v.icon) };
	}
	return out;
}

function readRoles(raw: unknown): Roles | null {
	if (!raw || typeof raw !== "object") return null;
	const r = raw as Record<string, unknown>;
	const out = {} as Roles;
	for (const role of ROLES) out[role] = typeof r[role] === "string" ? (r[role] as string) : "";
	return out;
}

/**
 * One write on the `DesksRef` node at `path`. Pure apart from the stores it
 * feeds (this module's and the router's), so it is testable.
 */
export function applyDesksWrite(path: Path | null, payload: unknown): void {
	if (path) at = path;
	// Idempotent: the router keeps sets, so these bind once, and again after a reset.
	onDeskWrite(push);
	onDeskDelete(deleteDesk);
	const p = (payload ?? {}) as Record<string, unknown>;
	const op = String(p.op ?? "");
	if (op === "set_desks") {
		shipped = readDesks(p.desks);
		for (const id of [...pending.keys()]) if (shipped[id]) pending.delete(id);
		desks = { ...Object.fromEntries(pending), ...shipped };
		order = Array.isArray(p.order) ? p.order.filter((x): x is string => typeof x === "string") : [];
		reorder();
		setDesks(desks);
		emit();
	} else if (op === "set_roles") {
		roles = readRoles(p.roles);
		setRoles(roles);
		emit();
	} else if (op === "set_titles") {
		titles = readTitles(p.titles);
		emit();
	}
}

// -- Reads --------------------------------------------------------------------

/** Every desk this tab knows, by id. Null until the first `set_desks`. */
export function useDesks(): Record<string, Desk> | null {
	return useSyncExternalStore(
		subscribe,
		() => desks,
		() => desks,
	);
}

/** The desk ids in creation order (Favorites first), as the sidebar draws them. Empty until the first `set_desks`. */
export function useDeskOrder(): string[] {
	return useSyncExternalStore(
		subscribe,
		() => ids,
		() => ids,
	);
}

/** The desk ids in order now, outside a render. */
export function deskOrder(): string[] {
	return ids;
}

/** The roles, role to plane id. Null until the first `set_roles`. */
export function useRoles(): Roles | null {
	return useSyncExternalStore(
		subscribe,
		() => roles,
		() => roles,
	);
}

/** The title and icon of every plane on a desk, by plane id. Empty until the first `set_titles`. */
export function useDeskTitles(): Record<string, PlaneLook> {
	return useSyncExternalStore(
		subscribe,
		() => titles,
		() => titles,
	);
}

/** The desk planes' titles now, outside a render. Empty until they land. */
export function currentTitles(): Record<string, PlaneLook> {
	return titles;
}

/** The roles now, outside a render. */
export function currentRoles(): Roles | null {
	return roles;
}

// -- Writes -------------------------------------------------------------------

/**
 * Delete a desk. Gone here at once; the next `set_desks` is the store's word.
 * The router's `closeDesk` is the way in from the ui: it also moves a tab on
 * the desk.
 */
export function deleteDesk(id: string): void {
	pending.delete(id);
	if (desks?.[id]) {
		const { [id]: _, ...rest } = desks;
		desks = rest;
		reorder();
		setDesks(desks);
		emit();
	}
	send("desk.delete", { desk_id: id });
}

/**
 * Move desk `id` in the sidebar's order, in front of desk `before`, last for
 * `""`. Moved here at once; the next `set_desks` is the store's word.
 */
export function moveDesk(id: string, before: string): void {
	if (id === before) return;
	const rest = ids.filter((d) => d !== id);
	const at = before ? rest.indexOf(before) : -1;
	rest.splice(at < 0 ? rest.length : at, 0, id);
	if (rest.every((d, i) => d === ids[i])) return;
	order = rest;
	reorder();
	emit();
	send("desk.move", { desk_id: id, before });
}

/** Point a role at a plane. */
export function setRole(role: Role, planeId: string): void {
	send("role.set", { role, plane_id: planeId });
}

/** Forget everything. Tests only. */
export function resetDesks(): void {
	at = null;
	shipped = null;
	pending.clear();
	desks = null;
	roles = null;
	titles = NO_TITLES;
	order = [];
	ids = [];
	emit();
}
