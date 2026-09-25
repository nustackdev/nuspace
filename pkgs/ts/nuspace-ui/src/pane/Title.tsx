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

import type * as React from "react";
import { useCallback, useEffect, useRef } from "react";
import { docTitle } from "../design";

/** A title is one line: newlines and runs of space collapse. */
function clean(text: string | null): string {
	return (text ?? "").replace(/\s+/g, " ").trim();
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
	compact,
	onCommit,
	onExit,
}: {
	/** The server's title. */
	value: string;
	placeholder: string;
	compact: boolean;
	/** A changed, non-empty title. */
	onCommit: (title: string) => void;
	/** Down or Enter at the end: hand the caret to the cells. False when there
	 *  is nowhere to go. */
	onExit?: () => boolean;
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
		[onExit],
	);

	return (
		// biome-ignore lint/a11y/useHeadingContent: the text is there, written by the effect above rather than rendered, so React never fights the caret for it
		<h1
			ref={ref}
			contentEditable
			suppressContentEditableWarning
			spellCheck={false}
			data-placeholder={placeholder}
			className={docTitle(compact)}
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
