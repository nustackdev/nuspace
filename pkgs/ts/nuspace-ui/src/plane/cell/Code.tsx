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
// and Escape has to hand control back to cell selection.
//
// The block says two things (ui-kit lib/save.ts): a change while you type and
// on blur, and a submit on shift+Enter. A cell's source is its program, so
// writing it reruns the cell, and the cell listens to the submit only. The
// changes are bookkeeping it ignores: a blur, an arrow out or Escape never
// touches the source. Until a submit the buffer is unsaved, the foot says so,
// and leaving the page asks first.

import { Code, type CodeProps, type FocusAt, Shortcut, useLeaveGuard } from "@nustackdev/ui-kit";
import { useCallback, useEffect, useRef, useState } from "react";
import { docSourceDot, docSourceFoot } from "../../design";
import type { FocusReq } from "../state";
import type { ExitDir } from "../types";

/** The live view the kit's block hands up through `onView`. */
type CodeView = NonNullable<Parameters<NonNullable<CodeProps["onView"]>>[0]>;

/** Where a request's caret goes in a source: its first line or its last,
 *  or wherever the editor's own selection already is. */
function sourceEdge(at: FocusAt): "start" | "end" | "kept" {
	if (at === "kept" || at === "start" || at === "end") return at;
	return at.edge === "first" ? "start" : "end";
}

const MIN_HEIGHT = 42;
const MAX_HEIGHT = 560;

export type CodeBoxProps = {
	source: string;
	focusReq: FocusReq | null;
	onFocusConsumed: () => void;
	/** Shift+Enter, the submit, and nothing else, changed or not. Reruns this cell only. */
	onCommit: (source: string) => void;
	onExit: (dir: ExitDir, column: number | undefined) => void;
	/** Back to cell selection. `unsaved`: the buffer differs from the source, so keep it open. */
	onEscape: (unsaved: boolean) => void;
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
	const cb = useRef({ onExit, onEscape, source });
	cb.current = { onExit, onEscape, source };

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
				cb.current.onEscape(!readOnly && view.state.doc.toString() !== cb.current.source);
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

	// A focus request, consumed once there is a view to take it. One that no
	// longer pulls (the caret went elsewhere meanwhile) is consumed in place.
	useEffect(() => {
		if (!view || !focusReq) return;
		if (!focusReq.pull) {
			onFocusConsumed();
			return;
		}
		const edge = sourceEdge(focusReq.at);
		if (edge !== "kept") {
			const doc = view.state.doc;
			const line = doc.line(edge === "start" ? 1 : doc.lines);
			const column = focusReq.column ?? (edge === "start" ? 0 : line.length);
			view.dispatch({
				selection: { anchor: line.from + Math.min(column, line.length) },
				scrollIntoView: true,
			});
		}
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
			onSubmit={onCommit}
			onDirty={onDirty}
			onView={setView}
		/>
	);
}

/** How long "saved" stays before the foot goes back to its hint. */
const SAVED_MS = 1500;

/**
 * A cell's source as the document shows it: the editor and its foot, which
 * says how to save, then "unsaved" while the buffer differs, then "saved" for
 * a moment once it went. A save reruns the cell, which its status shows.
 *
 * Dirty is a fact about the open buffer and about nothing else, so it is held
 * here rather than lifted into the cell.
 */
export function SourceEditor(props: Omit<CodeBoxProps, "onDirty">) {
	const { onCommit } = props;
	const [dirty, setDirty] = useState(false);
	const [saved, setSaved] = useState(false);
	useLeaveGuard(dirty && !props.readOnly);

	useEffect(() => {
		if (!saved) return;
		const t = window.setTimeout(() => setSaved(false), SAVED_MS);
		return () => window.clearTimeout(t);
	}, [saved]);

	// Read at commit time: a commit with nothing changed says nothing.
	const wasDirty = useRef(false);

	const commit = useCallback(
		(next: string) => {
			if (wasDirty.current) setSaved(true);
			wasDirty.current = false;
			setDirty(false);
			onCommit(next);
		},
		[onCommit],
	);

	const onDirty = useCallback((d: boolean) => {
		wasDirty.current = d;
		setDirty(d);
		if (d) setSaved(false);
	}, []);

	return (
		<>
			<CodeBox {...props} onCommit={commit} onDirty={onDirty} />
			{props.readOnly ? null : (
				<span className={docSourceFoot} data-source-foot="">
					{dirty ? (
						<>
							<span className={docSourceDot} aria-hidden="true" />
							unsaved
							<Shortcut keys={["shift", "enter"]} size="sm" />
							save
						</>
					) : saved ? (
						"saved"
					) : (
						<>
							<Shortcut keys={["shift", "enter"]} size="sm" />
							save
							<Shortcut keys={["esc"]} size="sm" />
							close
						</>
					)}
				</span>
			)}
		</>
	);
}
