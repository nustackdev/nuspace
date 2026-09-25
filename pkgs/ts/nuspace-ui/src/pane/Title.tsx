// The plane's title, renamed in place.
//
// Always editable, whatever the plane's `editable` says: that setting is about
// the plane's cells, not its name. The heading you read and the heading you
// type are the same `h1`, so there is no mode swap and no layout shift on
// click. The look is `docTitle`'s, placeholder included.
//
// Two rules make contenteditable behave under React:
//
//  1. React never owns the text. The element renders empty and an effect
//     writes `textContent`, and only while it is not focused, so a `set_plane`
//     that lands mid-edit never clobbers the draft or jumps the caret.
//  2. Escape and a no-op blur restore from the latest server value, read off
//     a ref, so a rename that landed while the field was focused shows up the
//     moment it lets go.
//
// Enter goes on writing below, the way a document does, when the plane below
// can take it. At the end of the title it opens a line at the top (`onOpen`),
// and Escape there brings the caret back to the title's end. Anywhere else it
// splits (`onSplit`): what follows the caret leaves the title and opens a text
// cell at the top, or with the caret at the start the title stays whole and
// the cell opens empty. The rename is saved as the caret leaves.

import type * as React from "react";
import { useCallback, useEffect, useRef } from "react";
import { docTitle } from "../design";

/** A title is one line: newlines and runs of space collapse. */
function clean(text: string | null): string {
	return (text ?? "").replace(/\s+/g, " ").trim();
}

/** `el`'s text either side of the caret, a selection dropped. */
function splitAtCaret(el: HTMLElement): [string, string] {
	const all = el.textContent ?? "";
	const sel = el.ownerDocument.getSelection();
	if (!sel || sel.rangeCount === 0) return [all, ""];
	const at = sel.getRangeAt(0);
	if (!el.contains(at.startContainer) || !el.contains(at.endContainer)) return [all, ""];
	const head = el.ownerDocument.createRange();
	head.selectNodeContents(el);
	head.setEnd(at.startContainer, at.startOffset);
	const tail = el.ownerDocument.createRange();
	tail.selectNodeContents(el);
	tail.setStart(at.endContainer, at.endOffset);
	return [head.toString(), tail.toString()];
}

/** The caret is collapsed at the very end of `el`'s text. */
function caretAtEnd(el: HTMLElement): boolean {
	const sel = el.ownerDocument.getSelection();
	if (!sel || sel.rangeCount === 0 || !sel.isCollapsed) return false;
	const at = sel.getRangeAt(0);
	if (!el.contains(at.endContainer)) return false;
	const tail = el.ownerDocument.createRange();
	tail.selectNodeContents(el);
	tail.setStart(at.endContainer, at.endOffset);
	return tail.toString().length === 0;
}

export function Title({
	value,
	placeholder,
	onCommit,
	onExit,
	onOpen,
	onSplit,
}: {
	/** The server's title. */
	value: string;
	placeholder: string;
	/** A changed, non-empty title. */
	onCommit: (title: string) => void;
	/** Down or Enter at the end: hand the caret to the cells. False when there
	 *  is nowhere to go. */
	onExit?: () => boolean;
	/** Enter at the end: open a line at the top, Escape there calling `home`.
	 *  False when there is nowhere to open one. */
	onOpen?: (home: () => void) => boolean;
	/** Enter elsewhere: open a text cell at the top holding `tail`. False when
	 *  there is nowhere to open one, and Enter leaves as it always did. */
	onSplit?: (tail: string) => boolean;
}) {
	const ref = useRef<HTMLHeadingElement | null>(null);
	const server = useRef(value);
	server.current = value;
	/** The text when the caret arrived, so a blur with no edit is no rename. */
	const entry = useRef(value);

	useEffect(() => {
		const el = ref.current;
		if (!el || el.ownerDocument.activeElement === el) return;
		if (el.textContent !== value) el.textContent = value;
	}, [value]);

	const commit = useCallback(() => {
		const el = ref.current;
		if (!el) return;
		const next = clean(el.textContent);
		const now = server.current;
		// Empty is not a rename, it is a mistake: the old title comes back.
		if (!next || next === clean(entry.current) || next === clean(now)) {
			el.textContent = now;
			return;
		}
		el.textContent = next;
		onCommit(next);
	}, [onCommit]);

	const onKeyDown = useCallback(
		(e: React.KeyboardEvent<HTMLHeadingElement>) => {
			if (e.nativeEvent.isComposing) return;
			const el = e.currentTarget;
			if (e.key === "Enter") {
				// Never a newline. Leaving commits, through the blur.
				e.preventDefault();
				const [head, tail] = splitAtCaret(el);
				const home = () => {
					el.focus();
					el.ownerDocument.getSelection()?.selectAllChildren(el);
					el.ownerDocument.getSelection()?.collapseToEnd();
				};
				if (clean(tail) === "" && onOpen?.(home)) return;
				const kept = clean(head) !== "";
				if (onSplit?.(kept ? clean(tail) : "")) {
					if (kept) el.textContent = head;
					return;
				}
				if (caretAtEnd(el) && onExit?.()) return;
				el.blur();
				return;
			}
			if (e.key === "Escape") {
				e.preventDefault();
				el.textContent = server.current;
				el.blur();
				return;
			}
			if (e.key === "ArrowDown" && caretAtEnd(el) && onExit?.()) e.preventDefault();
		},
		[onExit, onOpen, onSplit],
	);

	return (
		// biome-ignore lint/a11y/useHeadingContent: the text is there, written by the effect above rather than rendered, so React never fights the caret for it
		<h1
			ref={ref}
			contentEditable
			suppressContentEditableWarning
			spellCheck={false}
			data-placeholder={placeholder}
			className={docTitle()}
			onFocus={(e) => {
				entry.current = e.currentTarget.textContent ?? "";
			}}
			onBlur={commit}
			onKeyDown={onKeyDown}
			onInput={(e) => {
				// A browser leaves a stray `<br>` in an emptied field, which keeps
				// `:empty`, and with it the placeholder, from matching.
				const el = e.currentTarget;
				if (el.textContent === "" && el.firstChild) el.replaceChildren();
			}}
			// Rich text and newlines are not titles.
			onPaste={(e) => {
				e.preventDefault();
				const text = e.clipboardData.getData("text/plain").replace(/\s+/g, " ");
				document.execCommand("insertText", false, text);
			}}
		/>
	);
}
