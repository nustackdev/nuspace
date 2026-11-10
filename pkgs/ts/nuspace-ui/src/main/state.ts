// The ViewerRef node: what the wire writes into it.
//
// Every open Plane and its cells, as a map by plane id in `props.planes`: one
// entry replaced wholesale by that plane's `set_plane` and patched by its
// `set_status`. A pane with no Plane to draw gets a `set_absent` instead, kept
// by plane id in `props.absent`; either op replaces the other. Entries for
// Planes no longer open are dropped. The browser half of the node (each pane's
// editor state) is ../plane/state.ts.
//
// ## Cells are not registered here
//
// A cell's refs autovivify under the cell's own address the first time
// something writes to one, and the store disposes a subtree when it goes. All
// the browser knows about that address is ../plane/cell/address.ts.
//
// ## Why this type keeps a write handler
//
// Three ops ride one payload, told apart by an `op` key, and the store's default
// write has nothing to dispatch on. `set_status` also patches statuses into
// the cell list by id, which a prop merge cannot do, and `set_plane` has to
// prune local state naming cells the new Plane does not carry, which nothing
// else is in a position to notice.
//
// ## A closed plane leaves nothing drawn behind
//
// What a cell's run drew stays in the tree under the cell's address after its
// pane closes: nav stops the run, and nothing on the wire takes the drawing
// down. Reopened, the plane would draw it again the moment its `set_plane`
// lands, until the new run erases it and draws afresh. So the browser takes it
// down itself: a plane's cell ui goes when its pane closes, and a frame from
// the run that drew it is refused until the pane opens again (`admits`, on the
// socket). Reopening clears it once more before the plane is asked for, so a
// reopened plane always starts from nothing drawn.

import type { Frame, Path, Props } from "@nustackdev/ui-core";
import { nodeAt, pathKey, tree, useProps } from "@nustackdev/ui-kit";
import { useMemo } from "react";
import { LOCAL, localOf } from "../core/local";
import { cellUiPath } from "../plane/cell/address";
import { type EditorState, EMPTY_EDITOR, pruneEditor } from "../plane/state";
import {
	type AbsentReason,
	type ActivePlane,
	type CellSpec,
	type CellStatus,
	coerceAbsent,
	coerceCells,
	coerceMeta,
	coerceStatus,
} from "../plane/types";

/** Every open Plane that has landed, by id, off the node's props. */
function planesOf(props: Props): Record<string, ActivePlane> {
	return (props.planes as Record<string, ActivePlane> | undefined) ?? {};
}

/** Why each open pane has no Plane, by id, off the node's props. */
function absentOf(props: Props): Record<string, AbsentReason> {
	return (props.absent as Record<string, AbsentReason> | undefined) ?? {};
}

/** Every pane's editor state, by Plane id, off the node's props. */
function panesOf(props: Props): Record<string, EditorState> {
	return localOf<Record<string, EditorState>>(props, {});
}

/** Drop one entry. Same object when it is not there. */
function without<T>(byId: Record<string, T>, id: string): Record<string, T> {
	if (!(id in byId)) return byId;
	const { [id]: _, ...rest } = byId;
	return rest;
}

/** Keep only the entries for Planes in `open`. Same object when nothing goes. */
function keepOpen<T>(byId: Record<string, T>, open: string[]): Record<string, T> {
	const keys = Object.keys(byId);
	if (keys.every((k) => open.includes(k))) return byId;
	const out: Record<string, T> = {};
	for (const k of keys) if (open.includes(k)) out[k] = byId[k];
	return out;
}

// -- The write handler's body ------------------------------------------------

/**
 * Apply one inbound payload to this node's props. Pure given `open`, the
 * Planes open on the desk, so it is testable.
 *
 * Every op is keyed by plane. A `set_plane` or `set_absent` for a Plane that is
 * no longer open is a reply to a pane already closed and is dropped, and every
 * such write prunes what belongs to closed panes.
 */
export function applyViewerWrite(props: Props, payload: unknown, open: string[]): void {
	const p = (payload ?? {}) as Record<string, unknown>;
	const op = String(p.op ?? "");
	const planeId = String(p.plane_id ?? "");

	if (op === "set_status") {
		const planes = planesOf(props);
		const plane = planes[planeId];
		if (!plane) return;
		const byId = new Map<string, CellStatus>();
		for (const raw of Array.isArray(p.statuses) ? p.statuses : []) {
			const st = coerceStatus(raw);
			if (st?.cell_id) byId.set(st.cell_id, st);
		}
		if (byId.size === 0) return;
		props.planes = {
			...planes,
			[planeId]: {
				...plane,
				cells: plane.cells.map((b) =>
					byId.has(b.id) ? { ...b, status: byId.get(b.id) ?? b.status } : b,
				),
			} satisfies ActivePlane,
		};
		return;
	}

	if (op !== "set_plane" && op !== "set_absent") return;

	const planes = keepOpen(planesOf(props), open);
	const panes = keepOpen(panesOf(props), open);
	const absent = keepOpen(absentOf(props), open);
	if (!planeId || !open.includes(planeId)) {
		props.planes = planes;
		props.absent = absent;
		props[LOCAL] = panes;
		return;
	}

	if (op === "set_absent") {
		const reason = coerceAbsent(p.reason);
		if (!reason) return;
		props.planes = without(planes, planeId);
		props.absent = { ...absent, [planeId]: reason };
		props[LOCAL] = without(panes, planeId);
		return;
	}

	const cells = coerceCells(p.cells);
	props.planes = {
		...planes,
		[planeId]: {
			plane_id: planeId,
			title: String(p.title ?? ""),
			meta: coerceMeta(p.meta),
			cells,
		} satisfies ActivePlane,
	};
	props.absent = without(absent, planeId);

	const live = new Set(cells.map((b) => b.id));
	props[LOCAL] = { ...panes, [planeId]: pruneEditor(panes[planeId] ?? EMPTY_EDITOR, live) };
}

// -- Closed planes' cell ui ---------------------------------------------------

/** The cell ui of each closed plane, by plane id: taken down, and refused until it reopens. */
const closed = new Map<string, Path[]>();
/** Every path in `closed`, keyed, for the one lookup a frame costs. */
const refused = new Set<string>();
/** How deep a cell's ui address is. Every one is the same depth: one viewer. */
let cellDepth = 0;

function takeDown(ui: Path): void {
	if (nodeAt(ui)) tree.getState().remove(ui);
}

/**
 * Whether an inbound frame may land. False for one under the cell ui of a
 * closed plane: a late frame from the run its pane stopped, which would draw
 * it back into the tree for the next open to show.
 */
export function admits(frame: Frame): boolean {
	if (refused.size === 0 || frame.ref.length < cellDepth) return true;
	return !refused.has(pathKey(frame.ref.slice(0, cellDepth)));
}

/**
 * Take down the cell ui of planes that closed and refuse what still comes for
 * it; clear it again for planes that reopened and let them draw. Before the
 * open planes are asked for, so nothing a reopened plane shows predates it.
 */
function settleCellUi(path: Path, planes: Record<string, ActivePlane>, open: string[]): void {
	for (const id of open) {
		const uis = closed.get(id);
		if (!uis) continue;
		closed.delete(id);
		for (const ui of uis) {
			refused.delete(pathKey(ui));
			takeDown(ui);
		}
	}
	for (const [id, plane] of Object.entries(planes)) {
		if (open.includes(id)) continue;
		const uis = plane.cells.map((c) => cellUiPath(path, c.id));
		closed.set(id, uis);
		for (const ui of uis) {
			cellDepth = ui.length;
			refused.add(pathKey(ui));
			takeDown(ui);
		}
	}
}

/**
 * Drop the planes and editor state of panes that are no longer open, and the
 * cell ui of their planes (see above). Run when the route changes, before the
 * open planes are asked for, so a closed pane's data does not linger until
 * the next `set_plane` happens to prune it.
 */
export function pruneViewer(path: Path, open: string[]): void {
	const node = nodeAt(path);
	if (!node) return;
	const planes = planesOf(node.props);
	settleCellUi(path, planes, open);
	const panes = panesOf(node.props);
	const absent = absentOf(node.props);
	const nextPlanes = keepOpen(planes, open);
	const nextPanes = keepOpen(panes, open);
	const nextAbsent = keepOpen(absent, open);
	if (nextPlanes === planes && nextPanes === panes && nextAbsent === absent) return;
	tree.getState().setProps(path, { planes: nextPlanes, absent: nextAbsent, [LOCAL]: nextPanes });
}

/**
 * Merge `meta` into one plane's settings, locally. The optimistic half of a
 * `plane.web` flags write: the switch moves now, and the server's next `set_plane`
 * replaces the whole plane with what it actually stored.
 */
export function patchPlaneMeta(path: Path, planeId: string, meta: Record<string, unknown>): void {
	const node = nodeAt(path);
	if (!node) return;
	const planes = planesOf(node.props);
	const plane = planes[planeId];
	if (!plane) return;
	tree.getState().setProps(path, {
		planes: { ...planes, [planeId]: { ...plane, meta: coerceMeta({ ...plane.meta, ...meta }) } },
	});
}

/**
 * Set one plane's title, locally. The optimistic half of a rename from a tab:
 * the tab and the plane's heading change now, and the server's next
 * `set_plane` replaces the plane with what it actually stored.
 */
export function patchPlaneTitle(path: Path, planeId: string, title: string): void {
	const node = nodeAt(path);
	if (!node) return;
	const planes = planesOf(node.props);
	const plane = planes[planeId];
	if (!plane || plane.title === title) return;
	tree.getState().setProps(path, { planes: { ...planes, [planeId]: { ...plane, title } } });
}

// -- Reads -------------------------------------------------------------------

const NO_PLANES: Record<string, ActivePlane> = {};

/** Every open Plane that has landed, by id. A pane whose id is missing is
 *  still loading. */
export function usePlanes(path: Path): Record<string, ActivePlane> {
	return (useProps(path).planes as Record<string, ActivePlane> | undefined) ?? NO_PLANES;
}

const NO_ABSENT: Record<string, AbsentReason> = {};

/** Why each open pane has no Plane to draw, by id. */
export function useAbsent(path: Path): Record<string, AbsentReason> {
	return (useProps(path).absent as Record<string, AbsentReason> | undefined) ?? NO_ABSENT;
}

const EMPTY_CELL_SPECS: CellSpec[] = [];

/** The `/` menu's entries, in registry order, off the mount's props. */
export function useCellSpecs(path: Path): CellSpec[] {
	const raw = useProps(path).cell_specs;
	return useMemo(() => {
		if (!Array.isArray(raw)) return EMPTY_CELL_SPECS;
		const out: CellSpec[] = [];
		for (const r of raw) {
			if (!r || typeof r !== "object") continue;
			const o = r as Record<string, unknown>;
			const name = typeof o.name === "string" ? o.name : "";
			if (!name) continue;
			const label = typeof o.label === "string" && o.label ? o.label : name;
			const text = (k: string) => (typeof o[k] === "string" ? (o[k] as string) : "");
			const names = (k: string) => (Array.isArray(o[k]) ? (o[k] as unknown[]).map(String) : []);
			out.push({
				name,
				label,
				group: text("group"),
				icon: text("icon"),
				description: text("description"),
				classes: names("classes"),
				default_for: names("default_for"),
			});
		}
		return out.length ? out : EMPTY_CELL_SPECS;
	}, [raw]);
}
