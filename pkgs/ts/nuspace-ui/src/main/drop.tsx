// The canvas as a drop target: one set of handlers on what the canvas shows,
// and the target they aim at, which ./DropRegion.tsx draws (../desk/drag.ts
// has where a drop lands).
//
// Every kind of drag is taken (../desk/dnd.ts): a plane (a Planes tree or nav
// row, a solo pane's header), an item (a desk item row, a plane item's
// header) and a pane (a pane row, a pane header in a strip). Anything else
// dragged over the canvas (a file, a cell) passes through untouched. A drop
// goes out through `dropOn`, which does the drag table, and is offered only
// where the table writes something (`canDrop`, `canDropOnSolo`). Where the
// table refuses it for a reason (dnd `whyNot`: a plane a strip shows already,
// a whole strip), the region says why and the drop is not offered.
// Leaving the canvas, dropping or ending the drag anywhere clears the region.

import type * as React from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { paramsOf } from "../core/router";
import {
	canDrop,
	canDropOnSolo,
	dragging,
	dragKind,
	dropOn,
	dropOnSolo,
	readDrag,
	type Target,
	whyNot,
} from "../desk/dnd";
import { type Surface, sameTarget, targetAt } from "../desk/drag";

/** Where a drag event over `surface` points: the target, and why it is refused, if it is. */
type Aim = { target: Target; refused: string | null };

/** The aim of a drag event over `surface`, or null where it offers nothing. */
function aimOf(surface: Surface, e: React.DragEvent): Aim | null {
	if (!dragKind(e.dataTransfer)) return null;
	const target = targetAt(surface, e.target as Element, e.clientX, e.clientY, e.currentTarget);
	if (!target) return null;
	if (surface.kind === "solo") {
		return canDropOnSolo(dragging(), surface.plane) ? { target, refused: null } : null;
	}
	if (canDrop(dragging(), target)) return { target, refused: null };
	const refused = whyNot(dragging(), target);
	return refused ? { target, refused } : null;
}

/**
 * The canvas's drop handlers and the target they aim at. `surface` is what
 * the canvas shows, null for what takes no drop. A solo plane takes a drop
 * anywhere, making a new desk of the two.
 */
export function useCanvasDrop(surface: Surface | null): {
	aim: Target | null;
	/** Why the aim takes no drop, said on its region. Null for one that does. */
	refused: string | null;
	props: Pick<React.HTMLAttributes<HTMLElement>, "onDragOver" | "onDragLeave" | "onDrop">;
} {
	const [aim, setAim] = useState<Aim | null>(null);
	const show = useCallback(
		(next: Aim | null) =>
			setAim((was) =>
				sameTarget(was?.target ?? null, next?.target ?? null) && was?.refused === next?.refused
					? was
					: next,
			),
		[],
	);

	// A drag that ends anywhere (Esc, a drop elsewhere) clears the region.
	useEffect(() => {
		const clear = () => setAim(null);
		document.addEventListener("dragend", clear);
		document.addEventListener("drop", clear);
		return () => {
			document.removeEventListener("dragend", clear);
			document.removeEventListener("drop", clear);
		};
	}, []);

	// The surface by value: a new route object for the same view keeps the handlers.
	const key = surface ? JSON.stringify(surface) : "";
	// biome-ignore lint/correctness/useExhaustiveDependencies: the surface is compared by its key.
	const props = useMemo(() => {
		if (!surface) return {};
		return {
			onDragOver: (e: React.DragEvent) => {
				const next = aimOf(surface, e);
				show(next);
				if (!next || next.refused) return;
				e.preventDefault();
				e.dataTransfer.dropEffect = "move";
			},
			onDragLeave: (e: React.DragEvent) => {
				if (!e.currentTarget.contains(e.relatedTarget as Node | null)) show(null);
			},
			onDrop: (e: React.DragEvent) => {
				const at = aimOf(surface, e);
				show(null);
				if (!at || at.refused) return;
				const { target } = at;
				e.preventDefault();
				const payload = readDrag(e.dataTransfer);
				if (!payload) return;
				if (surface.kind === "solo") {
					if (target.kind === "onto") {
						dropOnSolo(
							payload,
							{ plane: surface.plane, params: paramsOf(surface.plane) },
							target.edge,
						);
					}
				} else dropOn(payload, target);
			},
		};
	}, [show, key]);

	return {
		aim: surface ? (aim?.target ?? null) : null,
		refused: surface ? (aim?.refused ?? null) : null,
		props,
	};
}
