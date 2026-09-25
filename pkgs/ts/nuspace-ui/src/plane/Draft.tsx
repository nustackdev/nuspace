// Type to create: a letter typed into a ghost, carried into a new text cell.
//
// The letter starts a cell from the text snippet and turns the ghost into a
// draft: plain text, held here in the browser, that keeps taking keys while
// the cell makes its round trip. When the cell's editor is ready the draft's
// text is typed into it through the browser's own insert, so the editor's
// normal change path is what saves it, and the draft goes. The caret lands
// where it stood in the draft.
//
// Enter mid-title comes through here too: a draft at the top, holding the
// title's tail, caret at its start. See ./useTextCells.ts.
//
// Ready is two real signals, never a timer:
//
//   - the cell's ui subtree holds a node with a string `value`, which is the
//     program's first write landing, and
//   - the cell's row holds an editable surface, which is the editor mounted
//     over that value.
//
// Either can come last, so both the tree store and the DOM are watched. The
// cell is found by the id minted here and nothing else, so another person's
// new cell never matches.
//
// Left out on purpose: an editor that never mounts leaves the draft standing,
// a reload loses it, and there is one draft at a time.

import type { Path, TreeNode } from "@nustackdev/ui-core";
import { nodeAt, pathKey, tree } from "@nustackdev/ui-kit";
import type * as React from "react";
import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { docDraft } from "../design";
import { cellUiPath } from "./cell/address";
import type { PlaneModel } from "./model";
import { hasText, type SlashSnippet, TEXT } from "./types";

/** What counts as a cell's editable text surface. The first one wins. */
const EDITABLE = '[contenteditable="true"], textarea, input';

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

/** The surface holds no text at all. */
export function surfaceEmpty(el: HTMLElement): boolean {
	return (isField(el) ? el.value : (el.textContent ?? "")) === "";
}

/** Focus a surface with the caret collapsed at its start or its end. */
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
	};
}

export type DraftState = {
	/** The cell it is waiting for, minted when the draft started. */
	id: string;
	/** The cell it sits after, null at the top of the plane. */
	after: string | null;
	/** What it opened with. The box holds the rest. */
	text: string;
	/** Where the caret opens in `text`. */
	caret: number;
};

/** Whether anything in this subtree holds a string `value`. */
function holdsValue(node: TreeNode | null): boolean {
	if (!node) return false;
	if (typeof node.props.value === "string") return true;
	for (const child of node.children.values()) if (holdsValue(child)) return true;
	return false;
}

export function useDraft(
	{ rootRef, patch }: PlaneModel,
	viewerPath: Path,
	snippets: SlashSnippet[],
	createAfter: (afterId: string | null, name: string, land?: boolean) => string,
) {
	const [draft, setDraft] = useState<DraftState | null>(null);
	const boxRef = useRef<HTMLTextAreaElement | null>(null);

	/**
	 * Start a text cell after `after`, holding `text` with the caret at
	 * `caret` (its end by default). False when one is already on its way.
	 * Null with no text snippet: the ghost opens the menu as before.
	 */
	const startDraft = !hasText(snippets)
		? null
		: (after: string | null, text: string, caret = text.length): boolean => {
				patch({ ghost: null, slash: null });
				if (draft) return false;
				// The draft owns the caret, so the cell is not landed on.
				setDraft({ id: createAfter(after, TEXT, false), after, text, caret });
				return true;
			};

	const viewerKey = pathKey(viewerPath);
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	useEffect(() => {
		if (!draft) return;
		const path = cellUiPath(viewerPath, draft.id);
		let done = false;
		const handoff = () => {
			const surface = cellSurface(rootRef.current, draft.id);
			if (done || !surface || !holdsValue(nodeAt(path))) return;
			done = true;
			const box = boxRef.current;
			const text = box ? box.value : draft.text;
			const at = box ? box.selectionStart : draft.caret;
			const prev = document.activeElement;
			const kept = box !== null && prev === box;
			// Drop the draft and show the cell now, so the surface can take focus.
			flushSync(() => setDraft(null));
			surface.focus();
			// What follows the caret goes in first and the caret goes back to
			// the start, so what precedes it lands before it and the caret ends
			// where it stood in the draft.
			const head = text.slice(0, at);
			const tail = text.slice(at);
			if (tail) {
				document.execCommand("insertText", false, tail);
				placeCaret(surface, "start");
			}
			if (head) document.execCommand("insertText", false, head);
			if (kept) return;
			// The caret went somewhere else meanwhile: the text lands, the caret
			// goes back. Leaving the editor is also what saves it.
			if (prev instanceof HTMLElement && prev !== document.body) prev.focus();
			else surface.blur();
		};
		const seen = new MutationObserver(handoff);
		if (rootRef.current) seen.observe(rootRef.current, { childList: true, subtree: true });
		const unsubscribe = tree.subscribe(handoff);
		return () => {
			seen.disconnect();
			unsubscribe();
		};
	}, [draft, viewerKey, rootRef]);

	return { draft, boxRef, startDraft };
}

/** The draft's box. Uncontrolled: it stays mounted until the handoff reads it. */
export function Draft({
	boxRef,
	text,
	caret,
}: {
	boxRef: React.RefObject<HTMLTextAreaElement | null>;
	text: string;
	caret: number;
}) {
	// biome-ignore lint/correctness/useExhaustiveDependencies: once, on mount
	useEffect(() => {
		const box = boxRef.current;
		if (!box) return;
		box.focus();
		box.setSelectionRange(caret, caret);
	}, []);

	return (
		<textarea
			ref={boxRef}
			aria-label="New text cell"
			rows={1}
			className={docDraft}
			defaultValue={text}
			// Its keys are its own, as a ghost's are.
			onKeyDown={(e) => e.stopPropagation()}
		/>
	);
}
