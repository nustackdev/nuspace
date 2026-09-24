// Monaco, wrapped so it owns exactly one program cell's source.
//
// Monaco is a text editor for a file. It has no idea a document exists, which
// is precisely why it is safe to borrow here: the cell boundary is the file
// boundary. Everything structural -- what comes before, what comes after,
// where the caret goes when it leaves -- is ours.
//
// The wrapper's real job is the boundary: ArrowUp on line 1 and ArrowDown on
// the last line have to leave the editor and land in the neighbouring cell,
// and Escape has to hand control back to cell selection.

import { Kbd } from "@nustackdev/ui-kit";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { docCodeBox, docSourceDirty } from "../../design";
import type { FocusReq } from "../state";
import type { ExitDir } from "../types";
import { type CodeEditor, type KeyboardEvt, loadMonaco, type MonacoApi, NU_THEME } from "./monaco";

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
};

export function CodeBox(props: CodeBoxProps) {
	const { source, focusReq, onFocusConsumed, onCommit, onExit, onEscape, onDirty } = props;

	const hostRef = useRef<HTMLDivElement | null>(null);
	const editorRef = useRef<CodeEditor | null>(null);
	const [ready, setReady] = useState(false);
	// Callbacks change identity every render; monaco listeners bind once.
	const cb = useRef({ onCommit, onExit, onEscape, onDirty });
	cb.current = { onCommit, onExit, onEscape, onDirty };
	const sourceRef = useRef(source);
	sourceRef.current = source;

	useLayoutEffect(() => {
		let disposed = false;
		let teardown: (() => void) | null = null;

		loadMonaco().then((monaco: MonacoApi) => {
			const host = hostRef.current;
			if (disposed || !host) return;

			const editor = monaco.editor.create(host, {
				value: sourceRef.current,
				language: "python",
				// One theme name; `monaco.ts` restains it in place on a flip.
				theme: NU_THEME,
				automaticLayout: true,
				minimap: { enabled: false },
				lineNumbers: "on",
				lineNumbersMinChars: 3,
				glyphMargin: false,
				folding: false,
				scrollBeyondLastLine: false,
				renderLineHighlight: "none",
				overviewRulerLanes: 0,
				hideCursorInOverviewRuler: true,
				scrollbar: {
					vertical: "auto",
					horizontal: "auto",
					alwaysConsumeMouseWheel: false,
				},
				padding: { top: 8, bottom: 8 },
				// Editor tier, one step under the document's 16px body type
				// (typography.md §2).
				fontSize: 13,
				fontFamily:
					getComputedStyle(document.documentElement).getPropertyValue("--font-mono") || "monospace",
				tabSize: 4,
				insertSpaces: true,
				wordWrap: "on",
				contextmenu: false,
				fixedOverflowWidgets: true,
				// Suggestions are off on purpose. There are no completion
				// providers wired, so the only thing on offer is word-based
				// noise -- and an open suggest widget owns ArrowUp/ArrowDown,
				// which is exactly the keys the cell boundary needs.
				quickSuggestions: false,
				suggestOnTriggerCharacters: false,
				wordBasedSuggestions: "off",
				parameterHints: { enabled: false },
			});
			editorRef.current = editor;

			const fit = () => {
				const h = Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, editor.getContentHeight()));
				host.style.height = `${h}px`;
				editor.layout({ width: host.clientWidth, height: h });
			};
			fit();

			const subs = [
				editor.onDidContentSizeChange(fit),
				editor.onDidChangeModelContent(() => {
					cb.current.onDirty(editor.getValue() !== sourceRef.current);
				}),
				editor.onKeyDown((e: KeyboardEvt) => {
					const pos = editor.getPosition();
					const model = editor.getModel();
					if (!pos || !model) return;
					const sel = editor.getSelection();
					const collapsed = !sel || sel.isEmpty();

					if (e.keyCode === monaco.KeyCode.Escape) {
						e.preventDefault();
						e.stopPropagation();
						cb.current.onCommit(editor.getValue());
						cb.current.onEscape();
						return;
					}
					if (e.keyCode === monaco.KeyCode.Enter && (e.metaKey || e.ctrlKey)) {
						e.preventDefault();
						e.stopPropagation();
						cb.current.onCommit(editor.getValue());
						return;
					}
					if (!collapsed) return;
					// A modifier means "move within this editor" (cmd+up = go to the
					// top of the file, shift+up = extend a selection, alt+up = move a
					// line). Only a bare arrow ever leaves the cell.
					const bare = !e.metaKey && !e.ctrlKey && !e.altKey && !e.shiftKey;
					if (!bare) return;
					if (e.keyCode === monaco.KeyCode.UpArrow && pos.lineNumber === 1) {
						e.preventDefault();
						e.stopPropagation();
						cb.current.onCommit(editor.getValue());
						cb.current.onExit("up", pos.column - 1);
						return;
					}
					if (e.keyCode === monaco.KeyCode.DownArrow && pos.lineNumber === model.getLineCount()) {
						e.preventDefault();
						e.stopPropagation();
						cb.current.onCommit(editor.getValue());
						cb.current.onExit("down", pos.column - 1);
					}
				}),
				editor.onDidBlurEditorText(() => {
					if (editor.getValue() !== sourceRef.current) {
						cb.current.onCommit(editor.getValue());
					}
				}),
			];

			teardown = () => {
				for (const s of subs) s.dispose();
				editor.getModel()?.dispose();
				editor.dispose();
				editorRef.current = null;
			};
			setReady(true);
		});

		return () => {
			disposed = true;
			teardown?.();
		};
	}, []);

	// Server-side source changed (our own save round-tripped, or someone else
	// wrote it). Only overwrite when the buffer is not being edited.
	useEffect(() => {
		const editor = editorRef.current;
		if (!editor) return;
		if (editor.getValue() !== source && !editor.hasTextFocus()) {
			editor.setValue(source);
			cb.current.onDirty(false);
		}
	}, [source]);

	useEffect(() => {
		const editor = editorRef.current;
		if (!editor || !focusReq || !ready) return;
		const model = editor.getModel();
		if (!model) return;
		const line = focusReq.place === "start" ? 1 : model.getLineCount();
		const max = model.getLineMaxColumn(line);
		const col =
			focusReq.column === undefined
				? focusReq.place === "start"
					? 1
					: max
				: Math.min(focusReq.column + 1, max);
		editor.setPosition({ lineNumber: line, column: col });
		editor.focus();
		editor.revealPositionInCenterIfOutsideViewport({
			lineNumber: line,
			column: col,
		});
		onFocusConsumed();
	}, [focusReq, onFocusConsumed, ready]);

	return <div ref={hostRef} className={docCodeBox} style={{ minHeight: MIN_HEIGHT }} />;
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
			{dirty ? (
				<span className={docSourceDirty}>
					unsaved
					<Kbd>⌘</Kbd>
					<Kbd>↵</Kbd>
				</span>
			) : null}
		</>
	);
}
