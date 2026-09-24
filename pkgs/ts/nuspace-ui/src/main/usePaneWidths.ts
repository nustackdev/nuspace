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
// Held in memory and keyed by the open pane set: open or close a pane and the
// widths go back to equal shares. Double-click a divider for the same.

import type * as React from "react";
import { useCallback, useState } from "react";
import { trackColDrag } from "../core/drag";
import { PANE_MIN_WIDTH } from "../design";

type Widths = { key: string; px: number[] };

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
	const key = routes.join("+");
	const split = routes.length > 1;
	const [state, setState] = useState<Widths | null>(null);
	const widths = state && state.key === key && state.px.length === routes.length ? state.px : null;

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

	const onResizeStart = useCallback(
		(e: React.PointerEvent, i: number) => {
			const strip = stripRef.current;
			if (!strip || i < 1) return;
			const panes = strip.querySelectorAll<HTMLElement>(":scope > [data-pane]");
			const start = Array.from(panes, (el) => el.getBoundingClientRect().width);
			if (start.length !== routes.length) return;
			const left = i - 1;
			const right = i;
			trackColDrag(e, (dx) => {
				const d = Math.max(dx, PANE_MIN_WIDTH - start[left]);
				const px = [...start];
				px[left] = start[left] + d;
				px[right] = Math.max(PANE_MIN_WIDTH, start[right] - d);
				setState({ key, px });
			});
		},
		[stripRef, routes.length, key],
	);

	const onResizeReset = useCallback(() => setState(null), []);

	return { styleOf, onResizeStart, onResizeReset };
}
