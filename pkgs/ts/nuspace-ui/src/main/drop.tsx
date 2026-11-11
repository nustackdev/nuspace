// The canvas as a drop target: one set of handlers on what the canvas shows,
// and the target they aim at, handed down to the parts that draw its line
// (../desk/drag.ts has where a drop lands).
//
// Every kind of drag is taken (../desk/dnd.ts): a plane (a Planes tree or nav
// row, a solo pane's header), an item (a desk item row, a plane item's
// header) and a pane (a pane row, a pane header in a strip). Anything else
// dragged over the canvas (a file, a cell) passes through untouched. A drop
// goes out through `dropOn`, which does the drag table, and is offered only
// where the table writes something (`canDrop`, `canDropOnSolo`).
// Leaving the canvas, dropping or ending the drag anywhere clears the line.

import type * as React from "react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
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
} from "../desk/dnd";
import { type Surface, sameTarget, targetAt } from "../desk/drag";

const Aim = createContext<Target | null>(null);

/** Where the drag in flight would land now, null at rest. */
export function useDropAim(): Target | null {
	return useContext(Aim);
}

export const DropAim = Aim.Provider;

/** The target a drag event over `surface` points at, or null when it offers none. */
function aimOf(surface: Surface, e: React.DragEvent): Target | null {
	if (!dragKind(e.dataTransfer)) return null;
	const target = targetAt(surface, e.target as Element, e.clientX, e.clientY, e.currentTarget);
	if (!target) return null;
	if (surface.kind === "solo") return canDropOnSolo(dragging(), surface.plane) ? target : null;
	return canDrop(dragging(), target) ? target : null;
}

/**
 * The canvas's drop handlers and the target they aim at. `surface` is what
 * the canvas shows, null for what takes no drop. A solo plane takes a drop
 * on its left or right edge, making a new desk of the two.
 */
export function useCanvasDrop(surface: Surface | null): {
	aim: Target | null;
	props: Pick<React.HTMLAttributes<HTMLElement>, "onDragOver" | "onDragLeave" | "onDrop">;
} {
	const [aim, setAim] = useState<Target | null>(null);
	const show = useCallback(
		(next: Target | null) => setAim((was) => (sameTarget(was, next) ? was : next)),
		[],
	);

	// A drag that ends anywhere (Esc, a drop elsewhere) clears the line.
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
				if (!next) return;
				e.preventDefault();
				e.dataTransfer.dropEffect = "move";
			},
			onDragLeave: (e: React.DragEvent) => {
				if (!e.currentTarget.contains(e.relatedTarget as Node | null)) show(null);
			},
			onDrop: (e: React.DragEvent) => {
				const target = aimOf(surface, e);
				show(null);
				if (!target) return;
				e.preventDefault();
				const payload = readDrag(e.dataTransfer);
				if (!payload) return;
				if (surface.kind === "solo") {
					if (target.kind === "onto") {
						dropOnSolo(
							payload,
							{ plane: surface.plane, params: paramsOf(surface.plane) },
							target.side,
						);
					}
				} else dropOn(payload, target);
			},
		};
	}, [show, key]);

	return { aim: surface ? aim : null, props };
}
