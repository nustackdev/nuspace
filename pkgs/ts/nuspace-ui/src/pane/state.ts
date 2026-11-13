// The PaneRef node: one open plane, at `<viewer>/panes/<plane>`. Mirrors
// `nuspace/web/viewer/ref.py` `PaneRef`.
//
// Everything one pane shows lives on its own node, and the pane reads that
// node and nothing else: its header, its `...` and its body. Five writes land
// here, each from its own watch on the server, so each keeps beside the
// others and any order is fine:
//
//   set_head    title, icon, key, system, editable, width. Clears an absent
//   set_cells   the cells in order, statuses folded in from what is kept
//   set_status  each cell's state, kept by cell id and folded into the cells
//   set_trail   the planes above, top first
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
import { type EditorState, EMPTY_EDITOR, pruneEditor } from "../plane/state";
import {
	type AbsentReason,
	type Cell,
	type CellStatus,
	type Crumb,
	coerceAbsent,
	coerceCells,
	coerceHead,
	coerceMeta,
	coerceStatus,
	coerceTrail,
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

const NO_TRAIL: Crumb[] = [];

/** The planes above the pane's, top first. Empty until it lands. */
export function usePaneTrail(path: Path): Crumb[] {
	return usePaneProp<Crumb[]>(path, "trail") ?? NO_TRAIL;
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
