// Waiting without flashing.
//
// Something that lands quickly should never show a placeholder for a frame
// and then snap to the real thing. So a placeholder waits: nothing at first,
// the placeholder only once the wait has run on past a threshold.
//
// One exception. When one skeleton goes and another comes straight after it
// (the boot skeleton handing over to a pane's, as the tree lands), the second
// shows at once, or the handover would blink through the blank wait.

import { useEffect, useState } from "react";

/** How long a plane (or the boot) may take before its skeleton stands in. */
export const SKELETON_DELAY_MS = 300;

/** How soon after one skeleton leaves the next one skips its wait. */
const HANDOFF_MS = 150;

let skeletonLeft = Number.NEGATIVE_INFINITY;

/** True once `active` has held for `ms` without a break. False while it is off. */
export function useAfter(active: boolean, ms: number): boolean {
	const [done, setDone] = useState(false);
	useEffect(() => {
		setDone(false);
		if (!active || ms <= 0) return;
		const timer = setTimeout(() => setDone(true), ms);
		return () => clearTimeout(timer);
	}, [active, ms]);
	return active && (ms <= 0 || done);
}

/**
 * Whether a skeleton mounted now should show yet: after
 * {@link SKELETON_DELAY_MS}, or at once when it takes over from another.
 */
export function useSkeleton(): boolean {
	const [handoff] = useState(() => performance.now() - skeletonLeft < HANDOFF_MS);
	const shown = useAfter(!handoff, SKELETON_DELAY_MS) || handoff;
	useEffect(() => {
		if (!shown) return;
		return () => {
			skeletonLeft = performance.now();
		};
	}, [shown]);
	return shown;
}
