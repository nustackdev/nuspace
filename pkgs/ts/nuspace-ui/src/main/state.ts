// The ViewerRef node: what the wire writes into it.
//
// Every open Plane and its cells, as a map by plane id in `props.planes`: one
// entry replaced wholesale by that plane's `set_plane` and patched by its
// `set_status`. Entries for Planes no longer open are dropped. The browser half
// of the node (each pane's editor state) is ../plane/state.ts.
//
// ## Cells are not registered here
//
// A cell's refs autovivify under the cell's own address the first time
// something writes to one, and the store disposes a subtree when it goes. All
// the browser knows about that address is ../plane/cell/address.ts.
//
// ## Why this type keeps a write handler
//
// Two ops ride one payload, told apart by an `op` key, and the store's default
// write has nothing to dispatch on. `set_status` also patches statuses into
// the cell list by id, which a prop merge cannot do, and `set_plane` has to
// prune local state naming cells the new Plane does not carry, which nothing
// else is in a position to notice.

import type { Path, Props } from "@nustackdev/ui-core";
import { nodeAt, tree, useProps } from "@nustackdev/ui-kit";
import { useMemo } from "react";
import { LOCAL, localOf } from "../core/local";
import { type EditorState, EMPTY_EDITOR, pruneEditor } from "../plane/state";
import {
	type ActivePlane,
	type CellStatus,
	coerceCells,
	coerceMeta,
	coerceStatus,
	type SlashSnippet,
} from "../plane/types";

/** Every open Plane that has landed, by id, off the node's props. */
function planesOf(props: Props): Record<string, ActivePlane> {
	return (props.planes as Record<string, ActivePlane> | undefined) ?? {};
}

/** Every pane's editor state, by Plane id, off the node's props. */
function panesOf(props: Props): Record<string, EditorState> {
	return localOf<Record<string, EditorState>>(props, {});
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
 * Planes the URL names, so it is testable.
 *
 * Both ops are keyed by plane. A `set_plane` for a Plane that is no longer open
 * is a reply to a pane already closed and is dropped, and every write prunes
 * what belongs to closed panes.
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

	if (op !== "set_plane") return;

	const planes = keepOpen(planesOf(props), open);
	const panes = keepOpen(panesOf(props), open);
	if (!planeId || !open.includes(planeId)) {
		props.planes = planes;
		props[LOCAL] = panes;
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

	const live = new Set(cells.map((b) => b.id));
	props[LOCAL] = { ...panes, [planeId]: pruneEditor(panes[planeId] ?? EMPTY_EDITOR, live) };
}

/**
 * Drop the planes and editor state of panes that are no longer open. Run when
 * the route changes, so a closed pane's data does not linger until the next
 * `set_plane` happens to prune it.
 */
export function pruneViewer(path: Path, open: string[]): void {
	const node = nodeAt(path);
	if (!node) return;
	const planes = planesOf(node.props);
	const panes = panesOf(node.props);
	const nextPlanes = keepOpen(planes, open);
	const nextPanes = keepOpen(panes, open);
	if (nextPlanes === planes && nextPanes === panes) return;
	tree.getState().setProps(path, { planes: nextPlanes, [LOCAL]: nextPanes });
}

/**
 * Merge `meta` into one plane's settings, locally. The optimistic half of a
 * `plane.meta`: the switch moves now, and the server's next `set_plane`
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

const EMPTY_SNIPPETS: SlashSnippet[] = [];

/** The `/` menu's entries, in registry order, off the mount's props. */
export function useSnippets(path: Path): SlashSnippet[] {
	const raw = useProps(path).snippets;
	return useMemo(() => {
		if (!Array.isArray(raw)) return EMPTY_SNIPPETS;
		const out: SlashSnippet[] = [];
		for (const r of raw) {
			if (!r || typeof r !== "object") continue;
			const o = r as Record<string, unknown>;
			const name = typeof o.name === "string" ? o.name : "";
			if (!name) continue;
			const label = typeof o.label === "string" && o.label ? o.label : name;
			out.push({ name, label });
		}
		return out.length ? out : EMPTY_SNIPPETS;
	}, [raw]);
}
