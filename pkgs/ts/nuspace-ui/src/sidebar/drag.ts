// Drag and drop in the Planes tree: reorder, nest and move to the top, all as
// one `plane.move`. And the parts every sidebar drop site shares: the bands
// of a row, the row under the pointer, and what a drop says.
//
// Native HTML5 drag and drop: the browser owns the threshold that tells a
// drag from a click, so a row stays an ordinary link until it is dragged.
//
// ## The drop language
//
// The desk's (../main/DropRegion.tsx): a light Afterglow wash in a 1.5px
// Afterglow line, saying what the drop does. In the sidebar it is one of two
// marks (./DropMarks.tsx):
//
//   the line    a drop between rows draws the accent line on the gap, from
//               the depth the row will land at, saying what happens on its
//               end ("Pin", "Move here", "New column")
//   the ring    a drop onto or into a row washes the row and says it at its
//               end ("Move inside", "Side by side")
//
// A hint never names a plane or a desk: a row is narrow and names run long.
// The wash already shows where.
//
// A drop the drag table refuses for a reason is a ring too, neutral and
// dashed, saying why ("Already in strip"), and is not offered. A drop that
// changes nothing shows nothing.
//
// ## Where a drop lands
//
// Read off the pointer against the row under it. A row the pointer has just
// reached is all middle: a drag sweeping over rows only rings them, and
// nothing reorders. Once it has rested on the row for `SETTLE_MS`
// (`useSettle`), the row's edges reorder (`bandAt`):
//
//   top 20%      before the row, the line above it
//   middle 60%   into the row, as its last child
//   bottom 20%   after the row, the line under it
//   below rows   the top level, last, at once
//
// Crossing from one row's edge to the next row's facing edge is the same
// gap: the line holds, with no new wait (`edgeHolds`).
//
// Between two rows of different depth the pointer's sideways travel since
// the drag began picks the depth (`seamTarget`): left by an indent step goes
// one level out, as far as the row under the gap allows. Unmoved, a drop
// before a row is its sibling, a drop after it is its sibling too, or its
// first child when it is open with children showing.
//
// No mark moves a row: the rows stay where they are drawn, so the bands are
// the row's own, exactly. The 1px gap between rows, and anything else over
// no row, keeps the aim (`rowAt`).
//
// A row can never land in its own subtree, itself included: those rows say
// so on the middle band and take no drop. Everything else moves, home and
// system Planes too. The server is the one that holds that rule; this only
// keeps from asking.
//
// A row can also be dropped on the desk or a desk folder, which read the
// drag's `PLANE_MIME` (../desk/dnd.ts). A nav row drags its plane the same way
// (`planeDragProps`), but never moves in the tree.

import type * as React from "react";
import { useCallback, useMemo, useRef, useState } from "react";
import {
	type Does,
	dropDoes,
	endDrag,
	type Payload,
	PLANE_MIME,
	type Target,
	writePlane,
} from "../desk/dnd";
import { setDragChip } from "../desk/drag";
import { anchorAt, type Notify } from "./ops";
import { subtreeOf, type VisibleRow } from "./tree";
import { childrenOf, type PlaneTree, ROOT_ID } from "./types";

export type DropEdge = "before" | "after" | "into";

/**
 * Where the dragged row would land. `key` "" is below the rows. `sibling`:
 * after the row as its sibling, even when it is open with children showing.
 */
export type DropTarget = { key: string; edge: DropEdge; sibling?: boolean };

/** What a row's drag carries: its plane id. The desk takes it too. */
export { PLANE_MIME };

// -- What a drop says ---------------------------------------------------------

/** The glyph a hint leads with. */
export type HintIcon = Does | "inside" | "refused";

/** What a drop mark says: a label and its glyph. */
export type Hint = { label: string; icon: HintIcon };

/** What a desk drop says (../desk/dnd.ts `dropDoes`). */
export function doesHint(payload: Payload | null, target: Target): Hint {
	const { does, label } = dropDoes(payload, target);
	return { label, icon: does };
}

/** Why a drop is refused. */
export function refusedHint(label: string): Hint {
	return { label, icon: "refused" };
}

/** Into a row of the dragged row's own subtree. */
const INTO_ITSELF = "Can't move into itself";

/**
 * What a tree move of `id` under `parent` says: back among its siblings,
 * out to the top level (a parent the tree does not draw, as a role plane,
 * counts as the top), or inside the parent. No names: the mark shows which.
 */
export function moveHint(tree: PlaneTree, rows: VisibleRow[], id: string, parent: string): Hint {
	if (parent === (tree[id]?.parent ?? ROOT_ID)) return { label: "Move here", icon: "move" };
	if (parent === ROOT_ID || !rows.some((r) => r.key === parent)) {
		return { label: "Move to top level", icon: "move" };
	}
	return { label: "Move inside", icon: "inside" };
}

// -- The row under the pointer -----------------------------------------------

/** On each drop row's box: its row key. */
export const DROP_ROW = "data-drop-row";

/** On the space under the last tree row. */
export const DROP_TAIL = "data-drop-tail";

/** One indent step of the tree, px: `sidebarIndent`'s 1.25rem. */
const INDENT_PX = 20;

/** The band a pointer `y` px down a row `height` px tall is in: 20 / 60 / 20. */
export function bandAt(y: number, height: number): DropEdge {
	const f = y / height;
	if (f < 0.2) return "before";
	if (f > 0.8) return "after";
	return "into";
}

/** How long the pointer rests on a row before its edges reorder, ms. */
export const SETTLE_MS = 300;

/**
 * Whether the pointer has rested on a row long enough for its edges to
 * reorder. `settled(key)` is asked on every dragover (which the browser
 * fires while the pointer is still too): a new row starts its wait, the same
 * row tells whether it is over. `reset` forgets the row, so coming back to it
 * waits again.
 */
export function useSettle(): { settled: (key: string) => boolean; reset: () => void } {
	const on = useRef<{ key: string; since: number } | null>(null);
	const settled = useCallback((key: string) => {
		const now = Date.now();
		if (on.current?.key !== key) {
			on.current = { key, since: now };
			return false;
		}
		return now - on.current.since >= SETTLE_MS;
	}, []);
	const reset = useCallback(() => {
		on.current = null;
	}, []);
	return { settled, reset };
}

/**
 * The band a drag uses on row `index`: its edge only once `rested`, or while
 * the line already drawn is on the gap that edge names (`gap`, under the
 * rows as `index` counts them), so crossing a gap keeps it. Else the middle.
 */
export function edgeHolds(
	band: DropEdge,
	index: number,
	rested: boolean,
	gap: number | null,
): DropEdge {
	if (band === "into" || rested) return band;
	return gap === (band === "before" ? index : index + 1) ? band : "into";
}

/**
 * The drop row (`DROP_ROW`) in `within` a drag event is over, as drawn, and
 * the pointer's `y` down it. Null over no row (the gap between rows, an
 * empty line): the aim holds.
 */
export function rowAt(
	e: Pick<React.DragEvent, "target" | "clientY">,
	within: Element,
): { el: HTMLElement; y: number; height: number } | null {
	const own = (e.target as Element | null)?.closest?.<HTMLElement>(`[${DROP_ROW}]`) ?? null;
	if (!own || !within.contains(own)) return null;
	const r = own.getBoundingClientRect();
	return { el: own, y: e.clientY - r.top, height: r.height };
}

// -- The tree's drop (pure) ---------------------------------------------------

/**
 * Where a drop in gap `gap` (before row `gap`; `rows.length` is under the
 * last) lands, at depth `want` as near as the gap allows, and the depth it
 * draws at. The gap allows from the row under it's depth (the top for none)
 * to the row over it's; under an open row with children showing, only its
 * first child's.
 */
export function seamTarget(
	rows: VisibleRow[],
	gap: number,
	want: number,
): { target: DropTarget; depth: number } {
	const above = rows[gap - 1];
	const below = rows[gap];
	if (!above) {
		return below
			? { target: { key: below.key, edge: "before" }, depth: below.depth }
			: { target: { key: "", edge: "after" }, depth: 0 };
	}
	if (below && below.parent === above.key) {
		return { target: { key: above.key, edge: "after" }, depth: below.depth };
	}
	const min = below ? below.depth : 0;
	const depth = Math.max(min, Math.min(above.depth, Number.isFinite(want) ? want : above.depth));
	if (depth === above.depth) {
		return { target: { key: above.key, edge: "after", sibling: true }, depth };
	}
	if (below && depth === below.depth) {
		return { target: { key: below.key, edge: "before" }, depth };
	}
	// Out of the row over the gap: after its ancestor at that depth.
	let at = above;
	while (at.depth > depth) {
		const up = rows.find((r) => r.key === at.parent);
		if (!up) break;
		at = up;
	}
	return { target: { key: at.key, edge: "after", sibling: true }, depth };
}

/**
 * Where a drop puts `id`: the parent and the index among the parent's
 * children, counted without `id`. Null when it would not move.
 */
export function dropMove(
	tree: PlaneTree,
	id: string,
	target: DropTarget,
	row: VisibleRow | undefined,
): { parent: string; index: number } | null {
	const without = (parent: string) =>
		childrenOf(tree, parent)
			.map((r) => r.id)
			.filter((k) => k !== id);
	let parent: string;
	let index: number;
	if (!target.key || !row) {
		parent = ROOT_ID;
		index = without(ROOT_ID).length;
	} else if (target.edge === "into") {
		parent = row.id;
		index = without(row.id).length;
	} else if (target.edge === "after" && row.open && row.hasKids && !target.sibling) {
		parent = row.id;
		index = 0;
	} else {
		parent = tree[row.id]?.parent ?? ROOT_ID;
		const sibs = without(parent);
		const at = sibs.indexOf(row.id);
		index = at < 0 ? sibs.length : target.edge === "after" ? at + 1 : at;
	}
	const from = tree[id]?.parent ?? "";
	if (from === parent && childrenOf(tree, parent).findIndex((r) => r.id === id) === index)
		return null;
	return { parent, index };
}

// -- The tree's drag ----------------------------------------------------------

/** How a tree aim shows: a ring on row `ring`, or the line on gap `gap` from `depth`. */
export type TreeMark = { ring: string } | { gap: number; depth: number };

/** Where a drag in the tree is aimed: the drop, its mark, what it says, whether it lands. */
export type TreeAim = { target: DropTarget; mark: TreeMark; hint: Hint; ok: boolean };

const sameAim = (a: TreeAim | null, b: TreeAim | null) => JSON.stringify(a) === JSON.stringify(b);

export function useTreeDrag({
	tree,
	rows,
	notify,
	reveal,
}: {
	tree: PlaneTree;
	rows: VisibleRow[];
	notify: Notify;
	reveal: (key: string) => void;
}) {
	const [dragKey, setDragKey] = useState<string | null>(null);
	const [aim, setAim] = useState<TreeAim | null>(null);
	// Where the drag began, sideways: travel from it picks a gap's depth.
	const startX = useRef(0);
	const { settled, reset } = useSettle();

	// The dragged row and everything under it: no drop lands there.
	const barred = useMemo(() => new Set(dragKey ? subtreeOf(tree, dragKey) : []), [tree, dragKey]);

	const show = useCallback(
		(next: TreeAim | null) => setAim((was) => (sameAim(was, next) ? was : next)),
		[],
	);

	const end = useCallback(() => {
		setDragKey(null);
		setAim(null);
		reset();
	}, [reset]);

	/** The aim of a drop on `target`, drawn as `mark`, or null where it moves nothing. */
	const judge = useCallback(
		(target: DropTarget, mark: TreeMark): TreeAim | null => {
			if (!dragKey || (target.key && barred.has(target.key))) return null;
			const move = dropMove(
				tree,
				dragKey,
				target,
				rows.find((r) => r.key === target.key),
			);
			if (!move) return null;
			return { target, mark, ok: true, hint: moveHint(tree, rows, dragKey, move.parent) };
		},
		[dragKey, barred, rows, tree],
	);

	/** The aim of a drag event over the tree; "keep" over no row, where the aim holds. */
	const aimAt = useCallback(
		(e: React.DragEvent<HTMLElement>): TreeAim | null | "keep" => {
			if (!dragKey) return null;
			if ((e.target as Element).closest?.(`[${DROP_TAIL}]`)) {
				const s = seamTarget(rows, rows.length, 0);
				return judge(s.target, { gap: rows.length, depth: s.depth });
			}
			const hit = rowAt(e, e.currentTarget);
			const i = hit ? rows.findIndex((r) => r.key === hit.el.getAttribute(DROP_ROW)) : -1;
			const row = rows[i];
			if (!hit || !row) return "keep";
			const rested = settled(row.key);
			const gap0 = aim && "gap" in aim.mark ? aim.mark.gap : null;
			const band = edgeHolds(bandAt(hit.y, hit.height), i, rested, gap0);
			if (band === "into") {
				if (row.key === dragKey) return null;
				const target: DropTarget = { key: row.key, edge: "into" };
				if (barred.has(row.key)) {
					return { target, mark: { ring: row.key }, ok: false, hint: refusedHint(INTO_ITSELF) };
				}
				return judge(target, { ring: row.key });
			}
			const gap = band === "before" ? i : i + 1;
			const travel = Math.round((e.clientX - startX.current) / INDENT_PX);
			const s = seamTarget(rows, gap, row.depth + (Number.isFinite(travel) ? travel : 0));
			return judge(s.target, { gap, depth: s.depth });
		},
		[dragKey, rows, barred, judge, settled, aim],
	);

	const drop = useCallback(
		(to: DropTarget) => {
			const id = dragKey;
			end();
			if (!id) return;
			const row = rows.find((r) => r.key === to.key);
			const move = dropMove(tree, id, to, row);
			if (!move) return;
			if (move.parent !== ROOT_ID) reveal(move.parent);
			const others = childrenOf(tree, move.parent)
				.map((r) => r.id)
				.filter((k) => k !== id);
			notify("plane.move", {
				plane_id: id,
				parent_id: move.parent,
				...anchorAt(others, move.index),
			});
		},
		[dragKey, rows, tree, notify, reveal, end],
	);

	/** Drag handlers for one row: it drags, the tree around it takes the drop. */
	const rowProps = useCallback(
		(key: string) => ({
			draggable: true,
			onDragStart: (e: React.DragEvent) => {
				setDragChip(e);
				writePlane(e.dataTransfer, key);
				startX.current = e.clientX;
				setDragKey(key);
			},
			onDragEnd: () => {
				endDrag();
				end();
			},
		}),
		[end],
	);

	/** Drop handlers around the rows, their gaps and the tail: leaving them, eg for the desk, drops the aim. */
	const zoneProps = useMemo(
		() => ({
			onDragOver: (e: React.DragEvent<HTMLElement>) => {
				if (!dragKey) return;
				const next = aimAt(e);
				if (next !== "keep") show(next);
				const now = next === "keep" ? aim : next;
				if (!now?.ok) return;
				e.preventDefault();
				e.stopPropagation();
				e.dataTransfer.dropEffect = "move";
			},
			onDragLeave: (e: React.DragEvent<HTMLElement>) => {
				if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
				show(null);
				reset();
			},
			onDrop: (e: React.DragEvent<HTMLElement>) => {
				if (!dragKey) return;
				const next = aimAt(e);
				const now = next === "keep" ? aim : next;
				if (!now?.ok) return;
				e.preventDefault();
				e.stopPropagation();
				drop(now.target);
			},
		}),
		[dragKey, aim, aimAt, show, drop, reset],
	);

	return { dragKey, aim, rowProps, zoneProps };
}

/** A row that drags its plane onto the desk or a desk folder, and nowhere in the tree. */
export function planeDragProps(plane: string) {
	return {
		draggable: true,
		onDragStart: (e: React.DragEvent) => {
			setDragChip(e);
			writePlane(e.dataTransfer, plane);
		},
		onDragEnd: endDrag,
	};
}
