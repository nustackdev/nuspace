// A plane dragged from the rail (a tree row or a pin) and dropped on the
// panes opens there as a split: the left half of a pane puts it before that
// pane, the right half after. A plane already open just takes focus, as
// "Open in split" does.
//
// Native drag and drop, the rail's own drags and their own data types. A tab
// dragged along the tab bar carries neither, so it never lands here.
//
// Capture phase, and a drop is stopped here: a cell's editor would otherwise
// take the drag's text (a pin is an anchor, and carries its URL) as a paste.

import type * as React from "react";
import { useEffect, useState } from "react";
import { openPaneAt } from "../core/router";
import { PIN_MIME } from "../sidebar/PinnedRow";
import { PLANE_MIME } from "../sidebar/useRailDrag";

export type PaneEdge = "before" | "after";

/** Where a drop would land: beside the pane showing `id`. */
export type PaneTarget = { id: string; edge: PaneEdge };

/** Whether a drag is a plane off the rail. */
function isPlaneDrag(e: React.DragEvent): boolean {
	const types = Array.from(e.dataTransfer.types);
	return types.includes(PLANE_MIME) || types.includes(PIN_MIME);
}

/** The half of `el` a pointer at `clientX` is over. */
export function edgeAt(el: Element, clientX: number): PaneEdge {
	const r = el.getBoundingClientRect();
	return clientX < r.left + r.width / 2 ? "before" : "after";
}

/** The index among `routes` a drop on `target` opens at. */
export function paneSlot(routes: string[], target: PaneTarget): number {
	const at = routes.indexOf(target.id);
	if (at < 0) return routes.length;
	return target.edge === "before" ? at : at + 1;
}

export function useCanvasDrop(routes: string[]) {
	const [target, setTarget] = useState<PaneTarget | null>(null);

	// A drag that ends anywhere else (Escape, a drop outside) drops the mark.
	useEffect(() => {
		if (!target) return;
		const clear = () => setTarget(null);
		window.addEventListener("dragend", clear);
		window.addEventListener("drop", clear);
		return () => {
			window.removeEventListener("dragend", clear);
			window.removeEventListener("drop", clear);
		};
	}, [target]);

	/** The pane under the pointer, or the last target over a gap (a divider). */
	const aim = (e: React.DragEvent): PaneTarget | null => {
		const pane = (e.target as Element).closest?.("[data-pane]");
		const id = pane?.getAttribute("data-pane");
		if (!pane || !id || !e.currentTarget.contains(pane)) return target;
		return { id, edge: edgeAt(pane, e.clientX) };
	};

	const dropProps = {
		onDragOverCapture: (e: React.DragEvent) => {
			if (!isPlaneDrag(e)) return;
			e.preventDefault();
			e.dataTransfer.dropEffect = "move";
			const next = aim(e);
			if (next?.id !== target?.id || next?.edge !== target?.edge) setTarget(next);
		},
		onDropCapture: (e: React.DragEvent) => {
			if (!isPlaneDrag(e)) return;
			e.preventDefault();
			e.stopPropagation();
			const to = aim(e);
			const id = e.dataTransfer.getData(PLANE_MIME) || e.dataTransfer.getData(PIN_MIME);
			setTarget(null);
			if (id && to) openPaneAt(id, paneSlot(routes, to));
		},
		onDragLeave: (e: React.DragEvent) => {
			if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setTarget(null);
		},
	};

	return { target, dropProps };
}
