// Pane share resizing, as numbers. The handles that drive it are
// ./Resize.tsx. A drag previews and writes once, on release.

/** The gap between columns, and between panes in a column, px. */
export const GAP = 6;

/** The shortest a pane gets while resizing, px: its header alone, the body collapsed. */
export const PANE_MIN = 34;

/** A pane resized under this, px, collapses to `PANE_MIN`: no sliver of a body. */
export const PANE_COLLAPSE = 100;

/**
 * The shares after the border under pane `index` moved `delta` px, in a
 * column whose panes have `room` px between them (its height without the
 * gaps). Only the two panes on the border change; neither gets under
 * `PANE_MIN`, and one that would get under `PANE_COLLAPSE` collapses to it.
 */
export function resizeShares(
	shares: readonly number[],
	index: number,
	delta: number,
	room: number,
): number[] {
	const out = [...shares];
	if (!(room > 0) || index < 0 || index + 1 >= shares.length) return out;
	const pair = shares[index] + shares[index + 1];
	const least = Math.min(PANE_MIN / room, pair / 2);
	const snap = PANE_COLLAPSE / room;
	let upper = Math.min(Math.max(shares[index] + delta / room, least), pair - least);
	if (upper < snap) upper = least;
	else if (pair - upper < snap) upper = pair - least;
	out[index] = upper;
	out[index + 1] = pair - upper;
	return out;
}
