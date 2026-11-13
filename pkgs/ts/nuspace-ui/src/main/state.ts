// The ViewerRef node: what every pane shares, and what goes when a pane closes.
//
// Each open plane is its own PaneRef node under `<viewer>/panes/<plane>`
// (../pane/state.ts): its head, cells, statuses, trail and editor state. The
// viewer keeps only what all panes share: the `/` menu's entries
// (`cell_specs`, seeded at boot) and the cell ui root, `<viewer>/cells/<cell>`,
// where every cell's refs autovivify (../plane/cell/address.ts).
//
// ## A closed pane goes at once
//
// The route changes first, here: a pane no longer open has its node dropped
// at once (`settlePanes`), before the server's erase comes back a round trip
// later. Both are safe; a write for it in between brings an empty node back
// for the erase to take.
//
// ## A closed plane leaves nothing drawn behind
//
// What a cell's run drew stays in the tree under the cell's address after its
// pane closes: nav stops the run, and nothing on the wire takes the drawing
// down. Reopened, the plane would draw it again the moment its cells land,
// until the new run erases it and draws afresh. So the browser takes it
// down itself: a plane's cell ui goes when its pane closes, and a frame from
// the run that drew it is refused until the pane opens again (`admits`, on the
// socket). Reopening clears it once more before the plane is asked for, so a
// reopened plane always starts from nothing drawn.

import type { Frame, Path } from "@nustackdev/ui-core";
import { nodeAt, pathKey, tree, useProps } from "@nustackdev/ui-kit";
import { useMemo } from "react";
import { PANES } from "../pane/state";
import { cellUiPath } from "../plane/cell/address";
import type { Cell, CellSpec } from "../plane/types";

// -- Closed panes --------------------------------------------------------------

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
 * Settle the panes against `open`, the planes the route shows now. Run when
 * the route changes, before the open planes are asked for.
 *
 * A pane no longer open has its node dropped, and its plane's cell ui taken
 * down and refused. A plane open again has its refusal lifted and what is
 * left of its cell ui cleared, so nothing a reopened plane shows predates it.
 */
export function settlePanes(viewerPath: Path, open: string[]): void {
	for (const id of open) {
		const uis = closed.get(id);
		if (!uis) continue;
		closed.delete(id);
		for (const ui of uis) {
			refused.delete(pathKey(ui));
			takeDown(ui);
		}
	}
	const panes = [...viewerPath, PANES];
	for (const [id, node] of nodeAt(panes)?.children ?? []) {
		if (open.includes(id)) continue;
		const cells = (node.props.cells as Cell[] | undefined) ?? [];
		const uis = cells.map((c) => cellUiPath(viewerPath, c.id));
		closed.set(id, uis);
		for (const ui of uis) {
			cellDepth = ui.length;
			refused.add(pathKey(ui));
			takeDown(ui);
		}
		tree.getState().remove([...panes, id]);
	}
}

// -- Reads -------------------------------------------------------------------

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
