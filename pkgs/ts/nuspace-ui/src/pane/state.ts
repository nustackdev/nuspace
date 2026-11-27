// The PaneRef node: one open plane, at `<viewer>/panes/<plane>`. Mirrors
// `nuspace/web/viewer/ref.py` `PaneRef`.
//
// Everything one pane shows lives on its own node, and the pane reads that
// node and nothing else: its header, its `...` and its body. Five writes land
// here, each from its own watch on the server, so each keeps beside the
// others and any order is fine:
//
//   set_head    title, icon, key, system, editable, width. Clears an absent
//   set_cells   the cells in order, statuses folded in from what is kept,
//               and the layout drawing them (../plane/types.ts `coerceLayout`)
//   set_status  each cell's state, kept by cell id and folded into the cells
//   set_trail   the planes above, top first
//   set_targets the answer to a `cell.targets` ask: where a cell can go
//               (../plane/transfer.ts). Null while asked and not answered
//   set_cell_info the answer to a `cell.info` ask: what one cell is and how
//               it last ran (../plane/cell/info.ts). Null while asked
//   set_absent  why there is nothing to draw. Stands in for the head
//   set_follow  whether the body follows its end (./scroll.ts)
//   scroll      one shot: the body to its top, end or a cell. A command
//               whose seq is the one held already is a replay, dropped
//
// So a rename reships the head and never a cell's source, and a cell edit
// reships the cells and never the head.
//
// The pane's editor state (caret, selection, the slash menu, ...) is the
// node's LOCAL slot (../plane/state.ts), so one pane's keystroke touches no
// other pane's node. `set_cells` prunes it of cells that went.
//
// The node comes with the first write and goes with the server's erase when
// the pane closes. The browser drops it itself first, on the route change
// (../main/state.ts `settlePanes`): both are safe, and the browser one does
// not wait a round trip.

import type { Path, Props } from "@nustackdev/ui-core";
import { getNode } from "@nustackdev/ui-core";
import { nodeAt, tree, useTree } from "@nustackdev/ui-kit";
import { LOCAL, localOf } from "../core/local";
import { type CellInfo, coerceCellInfo } from "../plane/cell/info";
import { type EditorState, EMPTY_EDITOR, pruneEditor } from "../plane/state";
import { coerceTargets, type Target } from "../plane/transfer";
import {
	type AbsentReason,
	type Cell,
	type CellStatus,
	type Crumb,
	coerceAbsent,
	coerceCells,
	coerceHead,
	coerceLayout,
	coerceMeta,
	coerceStatus,
	coerceTrail,
	type LayoutRow,
	type PaneHead,
} from "../plane/types";
import { coerceFollow, coerceScroll, type Follow, type ScrollCommand } from "./scroll";

/** The segment every pane hangs under, below the viewer. `PANES` in `nuspace/web/utils.py`. */
export const PANES = "panes";

/** Where the pane on `planeId` lives, under the ViewerRef node. */
export function panePath(viewerPath: Path, planeId: string): Path {
	return [...viewerPath, PANES, planeId];
}

// -- The write handler's body ------------------------------------------------

/** Cells with the kept statuses folded in. A cell with none keeps its own. */
function withStatuses(cells: Cell[], statuses: Record<string, CellStatus>): Cell[] {
	return cells.map((c) => (statuses[c.id] ? { ...c, status: statuses[c.id] } : c));
}

/** Apply one inbound payload to a pane node's props. Pure, so it is testable. */
export function applyPaneWrite(props: Props, payload: unknown): void {
	const p = (payload ?? {}) as Record<string, unknown>;
	const op = String(p.op ?? "");

	if (op === "set_head") {
		props.head = coerceHead(p);
		props.absent = undefined;
		return;
	}

	if (op === "set_cells") {
		const statuses = (props.statuses as Record<string, CellStatus> | undefined) ?? {};
		const cells = withStatuses(coerceCells(p.cells), statuses);
		props.cells = cells;
		props.layout = coerceLayout(p.layout, cells);
		const live = new Set(cells.map((c) => c.id));
		props[LOCAL] = pruneEditor(localOf<EditorState>(props, EMPTY_EDITOR), live);
		return;
	}

	if (op === "set_status") {
		const statuses: Record<string, CellStatus> = {};
		for (const raw of Array.isArray(p.statuses) ? p.statuses : []) {
			const st = coerceStatus(raw);
			if (st?.cell_id) statuses[st.cell_id] = st;
		}
		props.statuses = statuses;
		const cells = props.cells as Cell[] | undefined;
		if (cells) props.cells = withStatuses(cells, statuses);
		return;
	}

	if (op === "set_trail") {
		props.trail = coerceTrail(p.trail);
		return;
	}

	if (op === "set_absent") {
		const reason = coerceAbsent(p.reason);
		if (!reason) return;
		props.absent = reason;
		props.head = undefined;
		props[LOCAL] = EMPTY_EDITOR;
		return;
	}

	if (op === "set_targets") {
		props.targets = coerceTargets(p.planes);
		return;
	}

	if (op === "set_cell_info") {
		props.cellInfo = coerceCellInfo(p.info);
		return;
	}

	if (op === "set_follow") {
		props.follow = coerceFollow(p.follow);
		return;
	}

	if (op === "scroll") {
		const cmd = coerceScroll(p);
		if (!cmd || (props.scroll as ScrollCommand | undefined)?.seq === cmd.seq) return;
		props.scroll = cmd;
	}
}

/** Keep on the node that the command `seq` was applied, so it never applies again. */
export function markScrolled(path: Path, seq: string): void {
	if (nodeAt(path)?.props.scrolled === seq) return;
	tree.getState().setProps(path, { scrolled: seq });
}

// -- Optimistic patches --------------------------------------------------------

/**
 * Merge `meta` into the pane's settings, locally. The optimistic half of a
 * `plane.web` or `plane.icon`: the switch moves now, and the server's next
 * `set_head` replaces the head with what it actually stored.
 */
export function patchPaneMeta(path: Path, meta: Record<string, unknown>): void {
	const head = nodeAt(path)?.props.head as PaneHead | undefined;
	if (!head) return;
	tree.getState().setProps(path, {
		head: { ...head, meta: coerceMeta({ ...head.meta, ...meta }) },
	});
}

/** Set the pane's title, locally. The optimistic half of a `plane.rename`, like `patchPaneMeta`. */
export function patchPaneTitle(path: Path, title: string): void {
	const head = nodeAt(path)?.props.head as PaneHead | undefined;
	if (!head || head.title === title) return;
	tree.getState().setProps(path, { head: { ...head, title } });
}

/** Forget the last answer to `cell.targets`, locally, as a new ask goes out: loading until it lands. */
export function clearPaneTargets(path: Path): void {
	if (nodeAt(path)) tree.getState().setProps(path, { targets: null });
}

/** Forget the last answer to `cell.info`, locally, as a new ask goes out: loading until it lands. */
export function clearPaneCellInfo(path: Path): void {
	if (nodeAt(path)) tree.getState().setProps(path, { cellInfo: null });
}

// -- Reads -------------------------------------------------------------------
//
// One prop each, so a keystroke in the pane's editor state re-renders none
// of their readers.

function usePaneProp<T>(path: Path, key: string): T | undefined {
	return useTree((s) => getNode(s.root, path)?.props[key] as T | undefined);
}

/** The pane's head. Null until it lands, and while the pane is absent. */
export function usePaneHead(path: Path): PaneHead | null {
	return usePaneProp<PaneHead>(path, "head") ?? null;
}

/** The pane's cells with their statuses, in order. Null until they land. */
export function usePaneCells(path: Path): Cell[] | null {
	return usePaneProp<Cell[]>(path, "cells") ?? null;
}

/** How the pane's cells are drawn, as the last `set_cells` shipped it. Null until it lands. */
export function usePaneLayout(path: Path): LayoutRow[] | null {
	return usePaneProp<LayoutRow[]>(path, "layout") ?? null;
}

/** The layout on the pane at `path` as it is now, outside render: a drag reads its target's. */
export function paneLayout(path: Path): LayoutRow[] | null {
	return (nodeAt(path)?.props.layout as LayoutRow[] | undefined) ?? null;
}

/** The last answer to `cell.targets` on the pane at `path`, outside render. Null while none landed. */
export function paneTargets(path: Path): Target[] | null {
	return (nodeAt(path)?.props.targets as Target[] | undefined) ?? null;
}

const NO_TRAIL: Crumb[] = [];

/** The planes above the pane's, top first. Empty until it lands. */
export function usePaneTrail(path: Path): Crumb[] {
	return usePaneProp<Crumb[]>(path, "trail") ?? NO_TRAIL;
}

/** The answer to the last `cell.targets` ask. Null while none has landed since. */
export function usePaneTargets(path: Path): Target[] | null {
	return usePaneProp<Target[]>(path, "targets") ?? null;
}

/**
 * The answer to the last `cell.info` ask, when it is about `cellId`. Null
 * while none has landed since, and for an answer about another cell: a late
 * one for a menu closed since never shows under the next.
 */
export function useCellInfo(path: Path, cellId: string): CellInfo | null {
	return useTree((s) => {
		const info = getNode(s.root, path)?.props.cellInfo as CellInfo | null | undefined;
		return info?.cellId === cellId ? info : null;
	});
}

/** Whether the pane's body follows its end. "none" until told. */
export function usePaneFollow(path: Path): Follow {
	return usePaneProp<Follow>(path, "follow") ?? "none";
}

/** The newest one shot scroll command, null for none. */
export function usePaneScroll(path: Path): ScrollCommand | null {
	return usePaneProp<ScrollCommand>(path, "scroll") ?? null;
}

/** The seq of the command applied last, null for none. */
export function usePaneScrolled(path: Path): string | null {
	return usePaneProp<string>(path, "scrolled") ?? null;
}

/** Why the pane has nothing to draw, null when it has (or has not heard yet). */
export function usePaneAbsent(path: Path): AbsentReason | null {
	return usePaneProp<AbsentReason>(path, "absent") ?? null;
}
