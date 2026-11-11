// Drag and drop in the Planes tree: reorder, nest and move to the top, all as
// one `plane.move`.
//
// Native HTML5 drag and drop: the browser owns the threshold that tells a
// drag from a click, so a row stays an ordinary link until it is dragged.
//
// Where a drop lands is read off the pointer against the row under it:
//
//   top quarter      before the row, as its sibling
//   middle half      into the row, as its last child
//   bottom quarter   after the row, as its sibling (into it, first, when the
//                    row is open with children showing, since that is what
//                    sits right under the line)
//   below the rows   the top level, last
//
// A row can never land in its own subtree, itself included: those rows offer
// no drop at all. Everything else moves, home and system Planes too. The
// server is the one that holds that rule; this only keeps from asking.
//
// A row can also be dropped on the desk or a desk folder, which read the
// drag's `PLANE_MIME` (../desk/dnd.ts). A nav row drags its plane the same way
// (`planeDragProps`), but never moves in the tree.

import type * as React from "react";
import { useCallback, useMemo, useState } from "react";
import { endDrag, PLANE_MIME, writePlane } from "../desk/dnd";
import { setDragChip } from "../desk/drag";
import { anchorAt, type Notify } from "./ops";
import { subtreeOf, type VisibleRow } from "./tree";
import { childrenOf, type PlaneTree, ROOT_ID } from "./types";

export type DropEdge = "before" | "after" | "into";

/** Where the dragged row would land right now. `key` "" is below the rows. */
export type DropTarget = { key: string; edge: DropEdge };

/** What a row's drag carries: its plane id. The desk takes it too. */
export { PLANE_MIME };

/** The edge a pointer at `clientY` picks on `el`: top quarter, middle half, bottom quarter. */
export function edgeAt(el: HTMLElement, clientY: number): DropEdge {
	const r = el.getBoundingClientRect();
	const y = clientY - r.top;
	if (y < r.height / 4) return "before";
	if (y > (r.height * 3) / 4) return "after";
	return "into";
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
	} else if (target.edge === "after" && row.open && row.hasKids) {
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
	const [target, setTarget] = useState<DropTarget | null>(null);

	// The dragged row and everything under it: no drop lands there.
	const barred = useMemo(() => new Set(dragKey ? subtreeOf(tree, dragKey) : []), [tree, dragKey]);

	const end = useCallback(() => {
		setDragKey(null);
		setTarget(null);
	}, []);

	const drop = useCallback(
		(to: DropTarget) => {
			const id = dragKey;
			end();
			if (!id || barred.has(to.key)) return;
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
		[dragKey, barred, rows, tree, notify, reveal, end],
	);

	/** Handlers for one row. */
	const rowProps = useCallback(
		(key: string) => ({
			draggable: true,
			onDragStart: (e: React.DragEvent) => {
				setDragChip(e);
				writePlane(e.dataTransfer, key);
				setDragKey(key);
			},
			onDragEnd: () => {
				endDrag();
				end();
			},
			onDragOver: (e: React.DragEvent) => {
				if (!dragKey) return;
				if (barred.has(key)) {
					if (target) setTarget(null);
					return;
				}
				e.preventDefault();
				e.stopPropagation();
				e.dataTransfer.dropEffect = "move";
				const edge = edgeAt(e.currentTarget as HTMLElement, e.clientY);
				if (target?.key !== key || target.edge !== edge) setTarget({ key, edge });
			},
			onDrop: (e: React.DragEvent) => {
				if (!dragKey || barred.has(key)) return;
				e.preventDefault();
				e.stopPropagation();
				drop({ key, edge: edgeAt(e.currentTarget as HTMLElement, e.clientY) });
			},
		}),
		[dragKey, barred, target, drop, end],
	);

	/** Handlers for the space under the last row. */
	const tailProps = useMemo(
		() => ({
			onDragOver: (e: React.DragEvent) => {
				if (!dragKey) return;
				e.preventDefault();
				e.dataTransfer.dropEffect = "move";
				if (target?.key !== "") setTarget({ key: "", edge: "after" });
			},
			onDrop: (e: React.DragEvent) => {
				if (!dragKey) return;
				e.preventDefault();
				drop({ key: "", edge: "after" });
			},
		}),
		[dragKey, target, drop],
	);

	/** Handlers around the rows and the tail: leaving them, eg for the desk, drops the mark. */
	const leaveProps = useMemo(
		() => ({
			onDragLeave: (e: React.DragEvent) => {
				if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setTarget(null);
			},
		}),
		[],
	);

	return { dragKey, target, rowProps, tailProps, leaveProps };
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
