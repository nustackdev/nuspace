// The kit's code block, wrapped so it owns exactly one program cell's source.
//
// The block is an editor for one string. It has no idea a document exists,
// which is precisely why it fits here: the cell boundary is the string's
// boundary. Everything structural -- what comes before, what comes after,
// where the caret goes when it leaves -- is ours, bound on top of the live
// view the block hands up.
//
// The wrapper's real job is the boundary: ArrowUp on line 1 and ArrowDown on
// the last line have to leave the editor and land in the neighbouring cell,
// and Escape has to hand control back to cell selection. Saving is the
// block's own: cmd+enter and blur commit, and an arrow out is a blur. Escape
// closes the editor before a blur can land, so it commits for itself.

import { Code, type CodeProps, Shortcut } from "@nustackdev/ui-kit";
import { useCallback, useEffect, useRef, useState } from "react";
import { docSourceDirty } from "../../design";
import type { FocusReq } from "../state";
import type { ExitDir } from "../types";

/** The live view the kit's block hands up through `onView`. */
type CodeView = NonNullable<Parameters<NonNullable<CodeProps["onView"]>>[0]>;

const MIN_HEIGHT = 42;
const MAX_HEIGHT = 560;

export type CodeBoxProps = {
	source: string;
	focusReq: FocusReq | null;
	onFocusConsumed: () => void;
	/** Cmd+Enter, Escape, or blur with changes. Restarts this cell only. */
	onCommit: (source: string) => void;
	onExit: (dir: ExitDir, column: number | undefined) => void;
	onEscape: () => void;
	/** Live read of the buffer, for the parent's unsaved indicator. */
	onDirty: (dirty: boolean) => void;
	/**
	 * Show the source without letting it change: the block's read-only face,
	 * and nothing is ever committed. There is no caret to walk the lines, so
	 * the whole box is one stop: either arrow leaves it, and Escape still
	 * hands control back.
	 */
	readOnly?: boolean;
};

export function CodeBox(props: CodeBoxProps) {
	const { source, focusReq, onFocusConsumed, onCommit, onExit, onEscape, onDirty } = props;
	const readOnly = props.readOnly ?? false;

	const [view, setView] = useState<CodeView | null>(null);
	// Callbacks change identity every render; the key listener binds per view.
	const cb = useRef({ onCommit, onExit, onEscape, source });
	cb.current = { onCommit, onExit, onEscape, source };

	useEffect(() => {
		if (!view) return;
		// Read-only content is not focusable on its own, and a source the
		// caret cannot land in would strand the keyboard on the way past it.
		view.contentDOM.tabIndex = 0;

		const onKey = (e: KeyboardEvent) => {
			// A panel's own field (find) keeps its keys.
			if (e.target !== view.contentDOM) return;
			// An open completion list owns Escape and the arrows. The content
			// says one is open by naming the list it controls.
			if (view.contentDOM.hasAttribute("aria-controls")) return;
			const take = () => {
				e.preventDefault();
				e.stopPropagation();
			};

			if (e.key === "Escape") {
				take();
				const text = view.state.doc.toString();
				if (!readOnly && text !== cb.current.source) cb.current.onCommit(text);
				cb.current.onEscape();
				return;
			}
			if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
			// A modifier means "move within this editor" (cmd+up = go to the
			// top, shift+up = extend a selection, alt+up = move a line). Only
			// a bare arrow ever leaves the cell.
			if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return;
			const sel = view.state.selection.main;
			if (!sel.empty) return;
			const doc = view.state.doc;
			const line = doc.lineAt(sel.head);
			const up = e.key === "ArrowUp";
			if (!readOnly && line.number !== (up ? 1 : doc.lines)) return;
			take();
			cb.current.onExit(up ? "up" : "down", sel.head - line.from);
		};

		// Capture, so the boundary is decided before the editor's own keymap
		// moves the caret.
		view.dom.addEventListener("keydown", onKey, true);
		return () => view.dom.removeEventListener("keydown", onKey, true);
	}, [view, readOnly]);

	useEffect(() => {
		if (!view || !focusReq) return;
		const doc = view.state.doc;
		const line = doc.line(focusReq.place === "start" ? 1 : doc.lines);
		const column = focusReq.column ?? (focusReq.place === "start" ? 0 : line.length);
		view.dispatch({
			selection: { anchor: line.from + Math.min(column, line.length) },
			scrollIntoView: true,
		});
		view.focus();
		onFocusConsumed();
	}, [focusReq, onFocusConsumed, view]);

	return (
		<Code
			block
			value={source}
			language="python"
			readOnly={readOnly}
			lineNumbers
			wrap
			copyable
			minHeight={MIN_HEIGHT}
			maxHeight={MAX_HEIGHT}
			onCommit={onCommit}
			onDirty={onDirty}
			onView={setView}
		/>
	);
}

/**
 * A cell's source as the document shows it: the editor and the one reminder
 * that goes with it.
 *
 * Dirty is a fact about the open buffer and about nothing else, so it is held
 * here rather than lifted into the cell.
 */
export function SourceEditor(props: Omit<CodeBoxProps, "onDirty">) {
	const { onCommit } = props;
	const [dirty, setDirty] = useState(false);

	const commit = useCallback(
		(next: string) => {
			setDirty(false);
			onCommit(next);
		},
		[onCommit],
	);

	return (
		<>
			<CodeBox {...props} onCommit={commit} onDirty={setDirty} />
			{dirty && !props.readOnly ? (
				<span className={docSourceDirty}>
					unsaved
					<Shortcut keys={["mod", "enter"]} size="sm" />
				</span>
			) : null}
		</>
	);
}
