// Pane widths in a split: equal shares until somebody drags a divider.
//
// Before any drag every pane is `flex: 1 1 0` with the split minimum, so the
// panes share the strip equally and, when their minimums add up to more than
// the strip has, the strip scrolls.
//
// The first drag measures every pane and from then on each one's width is a
// number: `flex: w 0 w px`. Basis `w` so the drag moves exactly what it says;
// grow `w` so a wider window hands out the extra in proportion and the shape
// the person dragged survives; no shrink, so a narrower window scrolls rather
// than squeezing. A drag moves one border: the pane on its left takes `dx`
// down to its minimum, the pane on its right gives it back down to its own,
// and past that the strip just grows (and scrolls).
//
// Held in memory, by plane, and keyed by the open pane set but not its order:
// open or close a pane and the widths go back to equal shares, move one (a tab
// drag) and its width goes with it. Double-click a divider for the same reset.

import type * as React from "react";
import { useCallback, useState } from "react";
import { trackColDrag } from "../core/drag";
import { PANE_MIN_WIDTH } from "../design";

export type Widths = { key: string; px: Record<string, number> };

/** The pane set `routes` names, in any order. */
function setKey(routes: string[]): string {
	return [...routes].sort().join("+");
}

/** Each pane's width in `routes` order, or null for equal shares. */
export function widthsOf(state: Widths | null, routes: string[]): number[] | null {
	if (!state || state.key !== setKey(routes)) return null;
	const px = routes.map((id) => state.px[id]);
	return px.every((w) => w !== undefined) ? px : null;
}

export function usePaneWidths(
	stripRef: React.RefObject<HTMLElement | null>,
	routes: string[],
): {
	/** Pane `i`'s inline style. */
	styleOf: (i: number) => React.CSSProperties;
	/** Start dragging the divider on pane `i`'s left edge. */
	onResizeStart: (e: React.PointerEvent, i: number) => void;
	onResizeReset: () => void;
} {
	const split = routes.length > 1;
	const [state, setState] = useState<Widths | null>(null);
	const widths = widthsOf(state, routes);

	const styleOf = useCallback(
		(i: number): React.CSSProperties => {
			// A lone pane is the plane as it always was: the whole strip, no floor.
			if (!split) return { flex: "1 1 0px" };
			const w = widths?.[i];
			return w === undefined
				? { flex: "1 1 0px", minWidth: PANE_MIN_WIDTH }
				: { flex: `${w} 0 ${w}px`, minWidth: PANE_MIN_WIDTH };
		},
		[split, widths],
	);

	/** A click on a border (or a double-click) evens the panes out again. */
	const onResizeReset = useCallback(() => setState(null), []);

	const onResizeStart = useCallback(
		(e: React.PointerEvent, i: number) => {
			const strip = stripRef.current;
			if (!strip || i < 1) return;
			const panes = strip.querySelectorAll<HTMLElement>(":scope > [data-pane]");
			const start = Array.from(panes, (el) => el.getBoundingClientRect().width);
			if (start.length !== routes.length) return;
			const left = i - 1;
			const right = i;
			trackColDrag(
				e,
				(dx) => {
					const d = Math.max(dx, PANE_MIN_WIDTH - start[left]);
					const px: Record<string, number> = {};
					routes.forEach((id, j) => {
						px[id] = start[j];
					});
					px[routes[left]] = start[left] + d;
					px[routes[right]] = Math.max(PANE_MIN_WIDTH, start[right] - d);
					setState({ key: setKey(routes), px });
				},
				undefined,
				onResizeReset,
			);
		},
		[stripRef, routes, onResizeReset],
	);

	return { styleOf, onResizeStart, onResizeReset };
}
