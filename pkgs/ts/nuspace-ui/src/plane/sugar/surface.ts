// A cell's editable surface: the text field its program drew, found and
// driven from the outside. What the sugar reads (is it blank) and moves (the
// caret), without knowing what editor drew it.

/** What counts as a cell's editable text surface. The first one wins. */
export const EDITABLE = '[contenteditable="true"], textarea, input';

/**
 * A cell's editable text surface: the first one its program drew. Only the
 * drawn part counts, so an open source editor above it never does.
 */
export function cellSurface(root: HTMLElement | null, id: string): HTMLElement | null {
	return (
		root?.querySelector<HTMLElement>(`[data-cell="${id}"] [data-cell-ui] :is(${EDITABLE})`) ?? null
	);
}

function isField(el: HTMLElement): el is HTMLInputElement | HTMLTextAreaElement {
	return el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement;
}

/** One line of text, a paragraph or a heading. */
const LINE = /^(P|H[1-6])$/;

/**
 * The surface is blank: no text, and at most one empty line. Read off the
 * DOM, never the document: an empty table or a lone divider is not blank,
 * since what it holds is the structure.
 */
export function surfaceBlank(el: HTMLElement): boolean {
	if (isField(el)) return el.value === "";
	if ((el.textContent ?? "") !== "") return false;
	const only = el.firstElementChild;
	return (
		el.childElementCount === 0 || (el.childElementCount === 1 && LINE.test(only?.tagName ?? ""))
	);
}

/**
 * Focus a surface with the caret collapsed at its start or its end.
 *
 * An editor that keeps its own selection (ProseMirror) puts back the one it
 * last had a moment after it takes focus, unless it has read the new one by
 * then. The browser tells it on its own schedule, which can be late, and the
 * caret blinks to the old spot first. So it is told now.
 */
export function placeCaret(el: HTMLElement, at: "start" | "end"): void {
	el.focus();
	if (isField(el)) {
		const n = at === "start" ? 0 : el.value.length;
		el.setSelectionRange(n, n);
		return;
	}
	const sel = el.ownerDocument.getSelection();
	if (!sel) return;
	sel.selectAllChildren(el);
	if (at === "start") sel.collapseToStart();
	else sel.collapseToEnd();
	el.ownerDocument.dispatchEvent(new Event("selectionchange"));
}

/**
 * The caret as it stands in cell `id`'s surface, as a way back to it. The
 * exact spot when the text around it is still there, else the surface's end.
 */
export function keepCaret(root: HTMLElement | null, id: string): () => void {
	const el = cellSurface(root, id);
	const field = el && isField(el) ? [el.selectionStart, el.selectionEnd] : null;
	const sel = el?.ownerDocument.getSelection();
	const range = sel?.rangeCount ? sel.getRangeAt(0).cloneRange() : null;
	return () => {
		const now = cellSurface(root, id);
		if (!now) return;
		if (isField(now) && field) {
			now.focus();
			now.setSelectionRange(field[0], field[1]);
			return;
		}
		if (!range || !now.contains(range.startContainer) || !now.contains(range.endContainer)) {
			placeCaret(now, "end");
			return;
		}
		now.focus();
		const at = now.ownerDocument.getSelection();
		at?.removeAllRanges();
		at?.addRange(range);
		// Told now, as `placeCaret` does.
		now.ownerDocument.dispatchEvent(new Event("selectionchange"));
	};
}

/**
 * The collapsed caret, when it sits in `el`. With `head`, a selection's
 * moving end too, as a collapsed range: where Shift+arrow goes on from.
 */
function caretIn(el: HTMLElement, head = false): Range | null {
	const sel = el.ownerDocument.getSelection();
	if (!sel || sel.rangeCount === 0) return null;
	if (head && sel.focusNode) {
		if (!el.contains(sel.focusNode)) return null;
		const at = el.ownerDocument.createRange();
		at.setStart(sel.focusNode, sel.focusOffset);
		return at;
	}
	if (!sel.isCollapsed) return null;
	const at = sel.getRangeAt(0);
	return el.contains(at.startContainer) ? at : null;
}

/** The caret is in a table: its arrows and Cmd+Enter are the table's. */
export function caretInTable(el: HTMLElement, head = false): boolean {
	const at = caretIn(el, head);
	const node = at?.startContainer ?? null;
	const from = node instanceof Element ? node : (node?.parentElement ?? null);
	return from?.closest("table") != null && el.contains(from);
}

/** No text between the caret and `el`'s start (or end): Left or Right leaves. */
export function caretAtEdge(el: HTMLElement, side: "start" | "end", head = false): boolean {
	const at = caretIn(el, head);
	if (!at) return false;
	const rest = el.ownerDocument.createRange();
	rest.selectNodeContents(el);
	if (side === "start") rest.setEnd(at.startContainer, at.startOffset);
	else rest.setStart(at.startContainer, at.startOffset);
	return rest.toString() === "";
}

/** Where the caret draws. An empty line draws no caret box, so its line does. */
function caretBox(at: Range): DOMRect {
	const box = at.getBoundingClientRect();
	if (box.height > 0) return box;
	const node = at.startContainer;
	const line = node instanceof Element ? node : node.parentElement;
	return line?.getBoundingClientRect() ?? box;
}

/**
 * The caret is on `el`'s first (or last) line: Up or Down leaves. Read off
 * where things draw, so a wrapped paragraph counts its lines.
 */
export function caretOnEdgeLine(el: HTMLElement, side: "first" | "last", head = false): boolean {
	const at = caretIn(el, head);
	if (!at) return false;
	const caret = caretBox(at);
	const all = el.ownerDocument.createRange();
	all.selectNodeContents(el);
	const lines = all.getClientRects();
	const edge = lines.length
		? side === "first"
			? lines[0]
			: lines[lines.length - 1]
		: el.getBoundingClientRect();
	const half = caret.height / 2;
	return side === "first" ? caret.top < edge.top + half : caret.bottom > edge.bottom - half;
}
