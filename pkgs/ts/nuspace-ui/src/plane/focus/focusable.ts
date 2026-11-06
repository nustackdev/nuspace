// What on a plane can take the keyboard, shared by the two places that move it
// by hand: Enter into a selected cell that draws no markdown editor
// (./useFocusRouting.ts), and Tab off a selected cell
// (../selection/useCellKeys.ts). Everywhere else the browser's own tab order
// rules. A cell's markdown editor is never found this way: the kit hands
// its handle over (./useEditors.ts).

/** What a drawn cell can hand the keyboard to. */
export const FOCUSABLE = [
	'[contenteditable="true"]',
	"textarea",
	"input",
	"select",
	"button",
	"a[href]",
	'[tabindex]:not([tabindex="-1"])',
]
	.map((s) => `${s}:not([disabled])`)
	.join(", ");

/** In the tab order and on screen. */
function tabbable(el: HTMLElement): boolean {
	return el.tabIndex >= 0 && el.getClientRects().length > 0;
}

/**
 * The stop Tab reaches from a selected cell: the first tabbable after `from`
 * in the plane, or with `back` the last one before it, never one inside it.
 * Null when there is none, and the browser's own Tab carries on.
 *
 * A selected cell has no focus of its own, the plane root has it, so the
 * browser would start from the top of the plane instead.
 */
export function tabStop(root: HTMLElement, from: HTMLElement, back: boolean): HTMLElement | null {
	const side = back ? Node.DOCUMENT_POSITION_PRECEDING : Node.DOCUMENT_POSITION_FOLLOWING;
	const stops = [...root.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
		(el) => tabbable(el) && !from.contains(el) && from.compareDocumentPosition(el) & side,
	);
	return (back ? stops.at(-1) : stops[0]) ?? null;
}
