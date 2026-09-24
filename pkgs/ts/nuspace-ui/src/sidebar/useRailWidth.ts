// Drag-to-resize for the rail. The width lives in local state while dragging
// and lands in localStorage on release, so a reload keeps it. Storage can be
// missing or throw (private window, blocked site data), so every read and
// write is guarded and the rail falls back to the default.

import type * as React from "react";
import { useCallback, useState } from "react";
import { trackColDrag } from "../app/drag";
import { RAIL_WIDTH } from "../design";

const KEY = "nuspace.rail.width";

const clamp = (w: number) => Math.min(RAIL_WIDTH.MAX, Math.max(RAIL_WIDTH.MIN, Math.round(w)));

function load(): number {
	try {
		const raw = window.localStorage.getItem(KEY);
		const n = raw === null ? Number.NaN : Number(raw);
		return Number.isFinite(n) ? clamp(n) : RAIL_WIDTH.DEFAULT;
	} catch {
		return RAIL_WIDTH.DEFAULT;
	}
}

function save(w: number): void {
	try {
		window.localStorage.setItem(KEY, String(w));
	} catch {
		// nothing to do: the width just will not survive a reload
	}
}

export function useRailWidth(): {
	width: number;
	onResizeStart: (e: React.PointerEvent) => void;
	onResizeReset: () => void;
} {
	const [width, setWidth] = useState(load);

	const onResizeStart = useCallback(
		(e: React.PointerEvent) => {
			const startW = width;
			let last = startW;
			trackColDrag(
				e,
				(dx) => {
					last = clamp(startW + dx);
					setWidth(last);
				},
				() => save(last),
			);
		},
		[width],
	);

	/** Double-click the edge to snap back to the default. */
	const onResizeReset = useCallback(() => {
		setWidth(RAIL_WIDTH.DEFAULT);
		save(RAIL_WIDTH.DEFAULT);
	}, []);

	return { width, onResizeStart, onResizeReset };
}
