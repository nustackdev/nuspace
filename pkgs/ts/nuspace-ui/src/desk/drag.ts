// Drag and drop on the canvas side: what a pane header's drag carries, and
// where a drag over the canvas would land. The payloads, the targets and the
// one drop call are ./dnd.ts, shared with the sidebar.
//
// Native HTML5 drag and drop: the browser tells a drag from a click. A pane
// header drags as its row in the sidebar would (`PaneAt`):
//
//   in a strip      the pane (`writePane`: desk, item, plane)
//   a plane item    the item (`writeItem`: desk, item)
//   solo            the plane with the params it shows (`writePlane`)
//
// Where a drop lands is read off the pointer against what the canvas shows
// (`Surface`) and what is under the pointer:
//
//   the empty desk                    the end of the desk
//   a plane item, left / right edge   onto it: the two become a strip
//   in a strip, a pane's left / right quarter   a new column on that side
//   in a strip, a pane's middle half  its top or bottom half: stacked there
//   in a strip, the end zone (`[data-end]`)     a new column at the end
//
//   a solo plane, left / right edge   a new desk of the two (dnd `dropOnSolo`)
//
// Whether a target takes the drag is the drag table's (dnd `canDrop`).

import type * as React from "react";
import { paramsOf } from "../core/router";
import { dragChip } from "../design";
import { endDrag, type Target, writeItem, writePane, writePlane } from "./dnd";
import type { Drop, Edge, Side } from "./model";

/** Where a pane sits: solo, as a plane item, or in a strip. */
export type PaneAt =
	| { kind: "solo" }
	| { kind: "plane"; desk: string; item: string }
	| { kind: "strip"; desk: string; item: string };

/** What the canvas shows, as a drop surface: an empty desk, a plane item or a strip. */
export type Surface =
	/** A solo plane: a drop on its edge makes a new desk of the two (`dropOnSolo`). */
	| { kind: "solo"; plane: string }
	| { kind: "desk"; desk: string }
	| { kind: "plane"; desk: string; item: string }
	| { kind: "strip"; desk: string; item: string };

/** The share of a pane's width, from either side, that is its edge. */
export const EDGE_BAND = 1 / 4;

type Rect = Pick<DOMRect, "left" | "top" | "width" | "height">;

/** The drop target a pointer at (`x`, `y`) picks on a pane drawn at `rect`. */
export function edgeAt(rect: Rect, x: number, y: number): Edge {
	const fx = rect.width > 0 ? (x - rect.left) / rect.width : 0.5;
	if (fx < EDGE_BAND) return "left";
	if (fx > 1 - EDGE_BAND) return "right";
	return y - rect.top < rect.height / 2 ? "top" : "bottom";
}

/** The side of a plane item a pointer at `x` is on: its outer quarters only, null in the middle. */
export function sideAt(rect: Pick<Rect, "left" | "width">, x: number): Side | null {
	const fx = rect.width > 0 ? (x - rect.left) / rect.width : 0.5;
	if (fx < EDGE_BAND) return "left";
	if (fx > 1 - EDGE_BAND) return "right";
	return null;
}

/** The closest `sel` from `el`, kept only inside `within` when given. */
function inside(el: Element | null, sel: string, within?: Element): HTMLElement | null {
	const hit = el?.closest<HTMLElement>(sel) ?? null;
	return hit && (!within || within.contains(hit)) ? hit : null;
}

/**
 * Where a drop at (`x`, `y`) on `el` lands in a strip: an edge or half of the
 * pane it is in (`[data-pane]`), else the end zone (`[data-end]`, its column
 * index). Null off both. `within` bounds the lookup, so nothing outside the
 * canvas is read.
 */
export function dropAt(el: Element | null, x: number, y: number, within?: Element): Drop | null {
	const pane = inside(el, "[data-pane]", within);
	if (pane?.dataset.pane) {
		return { plane: pane.dataset.pane, edge: edgeAt(pane.getBoundingClientRect(), x, y) };
	}
	const end = inside(el, "[data-end]", within);
	const at = Number(end?.dataset.end);
	return end && Number.isInteger(at) && at >= 0 ? { at } : null;
}

/** Where a drop at (`x`, `y`) on `el` lands on `surface`, or null where it offers none. */
export function targetAt(
	surface: Surface,
	el: Element | null,
	x: number,
	y: number,
	within?: Element,
): Target | null {
	if (surface.kind === "desk") return { kind: "end", desk: surface.desk };
	if (surface.kind === "solo" || surface.kind === "plane") {
		const pane = inside(el, "[data-pane]", within);
		const side = pane ? sideAt(pane.getBoundingClientRect(), x) : null;
		if (!side) return null;
		// A solo plane has no desk yet: the target only says the side.
		if (surface.kind === "solo") return { kind: "onto", desk: "", item: "", side };
		return { kind: "onto", desk: surface.desk, item: surface.item, side };
	}
	const drop = dropAt(el, x, y, within);
	return drop ? { kind: "strip", desk: surface.desk, item: surface.item, drop } : null;
}

/** Whether two drops in a strip name the same target. */
export function sameDrop(a: Drop | null, b: Drop | null): boolean {
	if (!a || !b) return a === b;
	if ("at" in a) return "at" in b && a.at === b.at;
	if ("column" in a) return "column" in b && a.column === b.column;
	return "plane" in b && a.plane === b.plane && a.edge === b.edge;
}

/** Whether two targets name the same place. */
export function sameTarget(a: Target | null, b: Target | null): boolean {
	if (!a || !b) return a === b;
	if (a.kind !== b.kind || a.desk !== b.desk) return false;
	if (a.kind === "end") return true;
	if (a.kind === "between") return b.kind === "between" && a.index === b.index;
	if (a.kind === "onto") return b.kind === "onto" && a.item === b.item && a.side === b.side;
	return b.kind === "strip" && a.item === b.item && sameDrop(a.drop, b.drop);
}

/**
 * The one drag image, for every drag source: a chip (design `dragChip`) of
 * the icon marked `data-drag-icon` and the text marked `data-drag-title`
 * under the grabbed element, not the browser's snapshot of the whole thing.
 * Drawn off screen, taken as the image, removed once the drag has it. A
 * source with neither mark keeps the browser's image.
 */
export function setDragChip(e: React.DragEvent): void {
	const from = e.currentTarget;
	if (!(from instanceof HTMLElement) || !e.dataTransfer.setDragImage) return;
	const icon = from.querySelector("[data-drag-icon]");
	const text = from.querySelector("[data-drag-title]")?.textContent ?? "";
	if (!icon && !text) return;
	const chip = document.createElement("div");
	chip.className = dragChip;
	if (icon) chip.append(icon.cloneNode(true));
	const title = document.createElement("span");
	title.className = "truncate";
	title.textContent = text;
	chip.append(title);
	document.body.append(chip);
	e.dataTransfer.setDragImage(chip, 14, 14);
	setTimeout(() => chip.remove());
}

/** A pane header's drag handlers for the pane showing `plane` at `at`: it drags as its row would. */
export function headerDragProps(at: PaneAt, plane: string) {
	return {
		draggable: true,
		onDragStart: (e: React.DragEvent) => {
			setDragChip(e);
			if (at.kind === "strip") writePane(e.dataTransfer, at.desk, at.item, plane);
			else if (at.kind === "plane") writeItem(e.dataTransfer, at.desk, at.item);
			else writePlane(e.dataTransfer, { plane, params: paramsOf(plane) });
		},
		onDragEnd: endDrag,
	};
}
